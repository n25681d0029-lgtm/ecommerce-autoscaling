"""Cập nhật mã nguồn mới lên AWS mà KHÔNG phải xóa/tạo lại stack.

EC2 chỉ `git clone` mã nguồn lúc khởi động, nên sau khi `git push` code mới cần thay lần lượt
các instance. Script này gọi Instance Refresh của Auto Scaling Group: thay từng máy một, chờ máy mới
vượt qua health check rồi mới gỡ máy cũ, nên website không bị gián đoạn.

    python scripts/refresh_instances.py            # bắt đầu refresh và theo dõi tiến độ
    python scripts/refresh_instances.py --status   # chỉ xem tiến độ lần refresh gần nhất
"""
import argparse
import os
import sys
import time

import boto3
from botocore.exceptions import ClientError

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from dotenv_lite import load_env  # noqa: E402

DONE = {"Successful", "Failed", "Cancelled", "RollbackSuccessful", "RollbackFailed"}


def asg_name(sess, stack: str) -> str:
    outs = sess.client("cloudformation").describe_stacks(StackName=stack)["Stacks"][0]["Outputs"]
    return next(o["OutputValue"] for o in outs if o["OutputKey"] == "AutoScalingGroupName")


def show(r: dict) -> None:
    pct = r.get("PercentageComplete", 0)
    left = r.get("InstancesToUpdate", "?")
    print(f"  {time.strftime('%H:%M:%S')}  {r['Status']:<12} {pct:>3}%  còn {left} instance  {r.get('StatusReason', '')}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default=os.path.join(ROOT, "deploy.env"))
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--min-healthy", type=int, default=100,
                    help="%% instance phải khỏe trong lúc refresh (100 = thay từng máy, không giảm năng lực)")
    a = ap.parse_args()
    load_env(a.env)
    sess = boto3.Session(region_name=os.environ.get("AWS_REGION", "ap-southeast-1"))
    asg = sess.client("autoscaling")
    name = asg_name(sess, os.environ.get("STACK_NAME", "cloudshop"))

    if a.status:
        refs = asg.describe_instance_refreshes(AutoScalingGroupName=name, MaxRecords=1)["InstanceRefreshes"]
        if not refs:
            print("Chưa có lần refresh nào.")
        for r in refs:
            show(r)
        return

    try:
        rid = asg.start_instance_refresh(
            AutoScalingGroupName=name, Strategy="Rolling",
            # MaxHealthyPercentage > 100: ASG khởi động máy mới TRƯỚC rồi mới gỡ máy cũ
            # Thời gian warmup lấy theo DefaultInstanceWarmup (180 giây) đã đặt trong template
            Preferences={"MinHealthyPercentage": a.min_healthy, "MaxHealthyPercentage": 200,
                         "SkipMatching": False},
        )["InstanceRefreshId"]
    except ClientError as e:
        if e.response["Error"]["Code"] == "InstanceRefreshInProgress":
            sys.exit("Đang có một lần refresh chạy dở. Xem tiến độ: python scripts/refresh_instances.py --status")
        raise
    print(f"Bắt đầu Instance Refresh {rid} cho {name}. Mỗi máy mất khoảng 4–6 phút (cài đặt + warmup).")
    while True:
        r = asg.describe_instance_refreshes(AutoScalingGroupName=name, InstanceRefreshIds=[rid])["InstanceRefreshes"][0]
        show(r)
        if r["Status"] in DONE:
            break
        time.sleep(30)
    sys.exit(0 if r["Status"] == "Successful" else 1)


if __name__ == "__main__":
    main()
