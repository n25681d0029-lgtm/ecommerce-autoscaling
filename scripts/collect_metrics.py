"""Thu số liệu THẬT từ AWS trong lúc chạy kiểm thử tải, ghi ra CSV.

Mỗi chu kỳ (mặc định 60 giây) ghi lại:
  - Số instance mong muốn (desired) và số instance InService/khoẻ của Auto Scaling Group
  - CPU trung bình của nhóm (CloudWatch AWS/EC2, chu kỳ 1 phút, detailed monitoring)
  - Số request vào ALB/phút, thời gian phản hồi trung bình, số lỗi 5xx (AWS/ApplicationELB)

Ví dụ:
  python scripts/collect_metrics.py --stack cloudshop --region ap-southeast-1 --minutes 40
Kết quả: results/metrics_<thời điểm>.csv  -> dùng scripts/plot_metrics.py để vẽ biểu đồ.
"""
import argparse
import csv
import os
import time
from datetime import datetime, timedelta, timezone

import boto3


def stack_outputs(cf, stack: str) -> dict:
    out = cf.describe_stacks(StackName=stack)["Stacks"][0].get("Outputs", [])
    return {o["OutputKey"]: o["OutputValue"] for o in out}


def metric(cw, ns, name, dims, stat, start, end):
    r = cw.get_metric_statistics(Namespace=ns, MetricName=name, Dimensions=dims, StartTime=start,
                                 EndTime=end, Period=60, Statistics=[stat])
    pts = sorted(r["Datapoints"], key=lambda d: d["Timestamp"])
    return pts[-1][stat] if pts else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stack", default="cloudshop")
    ap.add_argument("--region", default="ap-southeast-1")
    ap.add_argument("--minutes", type=int, default=40, help="thời gian thu số liệu")
    ap.add_argument("--interval", type=int, default=60)
    a = ap.parse_args()

    sess = boto3.Session(region_name=a.region)
    cf, asg, cw = sess.client("cloudformation"), sess.client("autoscaling"), sess.client("cloudwatch")
    outs = stack_outputs(cf, a.stack)
    asg_name, lb, tg = outs["AutoScalingGroupName"], outs["LoadBalancerFullName"], outs["TargetGroupFullName"]

    os.makedirs("results", exist_ok=True)
    path = os.path.join("results", f"metrics_{datetime.now():%Y%m%d_%H%M}.csv")
    fields = ["time_utc", "desired", "in_service", "healthy", "cpu_avg", "requests_per_min",
              "resp_time_ms", "http_5xx"]
    print(f"Ghi vào {path}. Nhấn Ctrl+C để dừng sớm.")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        stop_at = time.time() + a.minutes * 60
        while time.time() < stop_at:
            now = datetime.now(timezone.utc)
            start = now - timedelta(minutes=4)
            g = asg.describe_auto_scaling_groups(AutoScalingGroupNames=[asg_name])["AutoScalingGroups"][0]
            insts = g["Instances"]
            lb_dims = [{"Name": "LoadBalancer", "Value": lb}]
            rt = metric(cw, "AWS/ApplicationELB", "TargetResponseTime", lb_dims, "Average", start, now)
            row = {
                "time_utc": now.strftime("%Y-%m-%d %H:%M:%S"),
                "desired": g["DesiredCapacity"],
                "in_service": sum(1 for i in insts if i["LifecycleState"] == "InService"),
                "healthy": sum(1 for i in insts if i["HealthStatus"] == "Healthy" and i["LifecycleState"] == "InService"),
                "cpu_avg": metric(cw, "AWS/EC2", "CPUUtilization",
                                  [{"Name": "AutoScalingGroupName", "Value": asg_name}], "Average", start, now),
                "requests_per_min": metric(cw, "AWS/ApplicationELB", "RequestCount", lb_dims, "Sum", start, now),
                "resp_time_ms": round(rt * 1000, 1) if rt is not None else None,
                "http_5xx": metric(cw, "AWS/ApplicationELB", "HTTPCode_Target_5XX_Count",
                                   lb_dims + [{"Name": "TargetGroup", "Value": tg}], "Sum", start, now) or 0,
            }
            w.writerow(row)
            f.flush()
            print(row)
            time.sleep(a.interval)
    print("Xong:", path)


if __name__ == "__main__":
    main()
