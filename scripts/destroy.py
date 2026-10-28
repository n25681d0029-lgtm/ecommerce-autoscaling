"""XÓA toàn bộ hạ tầng CloudShop để không phát sinh chi phí (EC2, ALB, RDS, IPv4...).

    python scripts/destroy.py          # hỏi xác nhận trước khi xóa
    python scripts/destroy.py --yes    # xóa luôn (dùng trên Kaggle)
"""
import argparse
import os
import sys

import boto3

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from dotenv_lite import load_env  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default=os.path.join(ROOT, "deploy.env"))
    ap.add_argument("--yes", action="store_true")
    a = ap.parse_args()
    load_env(a.env)
    region = os.environ.get("AWS_REGION", "ap-southeast-1")
    stack = os.environ.get("STACK_NAME", "cloudshop")
    if not a.yes and input(f"Xóa stack '{stack}' ở {region}? Gõ 'xoa' để xác nhận: ").strip() != "xoa":
        print("Đã hủy.")
        return
    cf = boto3.client("cloudformation", region_name=region)
    cf.delete_stack(StackName=stack)
    print("Đang xóa (khoảng 5–10 phút) ...")
    cf.get_waiter("stack_delete_complete").wait(StackName=stack, WaiterConfig={"Delay": 20, "MaxAttempts": 120})
    print("Đã xóa xong. Kiểm tra lại EC2 > Instances và RDS > Databases để chắc chắn không còn tài nguyên.")


if __name__ == "__main__":
    main()
