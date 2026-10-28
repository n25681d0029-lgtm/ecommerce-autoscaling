"""In lịch sử hoạt động co giãn THẬT của Auto Scaling Group (thời điểm thêm/bớt instance).

    python scripts/scaling_activities.py --stack cloudshop --region ap-southeast-1
Xuất thêm results/scaling_activities.csv để đưa vào bảng kết quả của báo cáo.
"""
import argparse
import csv
import os

import boto3


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stack", default="cloudshop")
    ap.add_argument("--region", default="ap-southeast-1")
    ap.add_argument("--max", type=int, default=30)
    a = ap.parse_args()
    sess = boto3.Session(region_name=a.region)
    outs = sess.client("cloudformation").describe_stacks(StackName=a.stack)["Stacks"][0]["Outputs"]
    asg_name = next(o["OutputValue"] for o in outs if o["OutputKey"] == "AutoScalingGroupName")
    acts = sess.client("autoscaling").describe_scaling_activities(AutoScalingGroupName=asg_name,
                                                                  MaxRecords=a.max)["Activities"]
    os.makedirs("results", exist_ok=True)
    with open("results/scaling_activities.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["start_utc", "end_utc", "status", "description", "cause"])
        for x in reversed(acts):
            row = [x["StartTime"].strftime("%Y-%m-%d %H:%M:%S"),
                   x.get("EndTime").strftime("%Y-%m-%d %H:%M:%S") if x.get("EndTime") else "",
                   x["StatusCode"], x["Description"], x["Cause"]]
            w.writerow(row)
            print(f"{row[0]}  {row[2]:<12} {row[3]}")
    print("Đã ghi results/scaling_activities.csv")


if __name__ == "__main__":
    main()
