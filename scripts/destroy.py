"""XÓA toàn bộ hạ tầng CloudShop để không phát sinh chi phí (EC2, ALB, RDS, IPv4, S3, CloudFront...).

Trước khi xóa, sản phẩm và ảnh trên S3 được SAO LƯU về thư mục catalog/ trong repo, nên những gì đã sửa
trên website AWS không mất: commit thư mục catalog/ lên git, lần triển khai sau (hoặc run_local.py
trên máy khác) sẽ nạp lại đúng dữ liệu đó.

    python scripts/destroy.py          # hỏi xác nhận trước khi xóa
    python scripts/destroy.py --yes    # xóa luôn (dùng trên Kaggle)
    python scripts/destroy.py --no-backup   # không sao lưu catalog (không khuyến khích)
"""
import argparse
import os
import sys

import boto3
from botocore.exceptions import ClientError, WaiterError

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from dotenv_lite import load_env  # noqa: E402
from envfile import clear_media_env  # noqa: E402


def stack_bucket(cf, stack: str) -> str | None:
    try:
        outs = cf.describe_stacks(StackName=stack)["Stacks"][0].get("Outputs", [])
    except ClientError:
        return None
    return next((o["OutputValue"] for o in outs if o["OutputKey"] == "MediaBucketName"), None)


def backup_catalog(s3, bucket: str, dest: str) -> int:
    """Tải catalog.json và các ảnh còn thiếu từ bucket về thư mục catalog/."""
    n = 0
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key != "catalog.json" and not key.startswith("images/"):
                continue
            path = os.path.join(dest, *key.split("/"))
            if key.startswith("images/") and os.path.exists(path):
                continue  # tên ảnh là mã băm nội dung: đã có là giống hệt
            os.makedirs(os.path.dirname(path), exist_ok=True)
            s3.download_file(bucket, key, path)
            n += 1
    return n


def empty_bucket(s3, bucket: str) -> int:
    """CloudFormation không xóa được bucket còn file, nên làm trống trước."""
    n = 0
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket):
        objs = [{"Key": o["Key"]} for o in page.get("Contents", [])]
        if objs:
            s3.delete_objects(Bucket=bucket, Delete={"Objects": objs, "Quiet": True})
            n += len(objs)
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default=os.path.join(ROOT, "deploy.env"))
    ap.add_argument("--yes", action="store_true")
    ap.add_argument("--no-backup", action="store_true")
    a = ap.parse_args()
    load_env(a.env)
    region = os.environ.get("AWS_REGION", "ap-southeast-1")
    stack = os.environ.get("STACK_NAME", "cloudshop")
    if not a.yes and input(f"Xóa stack '{stack}' ở {region}? Gõ 'xoa' để xác nhận: ").strip() != "xoa":
        print("Đã hủy.")
        return
    cf = boto3.client("cloudformation", region_name=region)
    s3 = boto3.client("s3", region_name=region)
    bucket = stack_bucket(cf, stack)
    if bucket:
        if not a.no_backup:
            dest = os.path.join(ROOT, "catalog")
            n = backup_catalog(s3, bucket, dest)
            print(f"Đã sao lưu {n} file từ s3://{bucket} về {dest}")
            print("  -> Nhớ commit & push thư mục catalog/ lên git để giữ lại sản phẩm và ảnh.")
        print(f"Đã làm trống bucket ({empty_bucket(s3, bucket)} file).")
    cf.delete_stack(StackName=stack)
    print("Đang xóa (khoảng 5–15 phút, CloudFront thường lâu nhất) ...")
    waiter = cf.get_waiter("stack_delete_complete")
    try:
        waiter.wait(StackName=stack, WaiterConfig={"Delay": 20, "MaxAttempts": 120})
    except WaiterError:
        if not bucket:
            raise
        # EC2 còn chạy trong lúc xóa có thể đã ghi lại catalog.json vào bucket -> làm trống lần nữa rồi xóa lại
        print(f"Xóa bucket chưa được, làm trống lại ({empty_bucket(s3, bucket)} file) và thử lần 2 ...")
        cf.delete_stack(StackName=stack)
        waiter.wait(StackName=stack, WaiterConfig={"Delay": 20, "MaxAttempts": 120})
    if clear_media_env():
        print("Đã gỡ S3_BUCKET khỏi .env: run_local.py quay về dùng thư mục catalog/.")
    print("Đã xóa xong. Kiểm tra lại EC2 > Instances và RDS > Databases để chắc chắn không còn tài nguyên.")


if __name__ == "__main__":
    main()
