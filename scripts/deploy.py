"""Triển khai (hoặc cập nhật) toàn bộ hạ tầng CloudShop bằng CloudFormation qua boto3.

Chạy được cả trên Windows (VS Code) lẫn Kaggle/Linux.
Tham số đọc từ file deploy.env (copy từ deploy.env.example rồi điền).

    python scripts/deploy.py              # tạo hoặc cập nhật stack, chờ hoàn tất, in URL website
    python scripts/deploy.py --status     # chỉ xem trạng thái + outputs
"""
import argparse
import os
import sys
import time

import boto3
from botocore.exceptions import ClientError, WaiterError

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from dotenv_lite import load_env  # noqa: E402

sys.path.insert(0, os.path.join(ROOT, "scripts"))
from envfile import write_media_env  # noqa: E402

CAPS = ["CAPABILITY_IAM"]  # template tạo IAM role cho EC2 truy cập bucket ảnh

PARAM_KEYS = ["GitRepoUrl", "GitBranch", "AppSubdir", "InstanceType", "MinSize", "MaxSize", "DesiredCapacity",
              "CpuTargetValue", "RequestsPerTargetValue", "DBEngineVersion", "DBUsername", "DBPassword", "AppSecretKey", "AdminPassword",
              "NotificationEmail"]


def print_outputs(cf, stack) -> dict:
    s = cf.describe_stacks(StackName=stack)["Stacks"][0]
    print(f"\nTrạng thái stack: {s['StackStatus']}")
    outs = {o["OutputKey"]: o["OutputValue"] for o in s.get("Outputs", [])}
    for k, v in outs.items():
        print(f"  {k:<24} {v}")
    return outs


def link_local_env(outs: dict, region: str) -> None:
    """Ghi bucket/CloudFront vào .env: run_local.py trên máy này sẽ dùng chung sản phẩm và ảnh với AWS."""
    if not outs.get("MediaBucketName"):
        return
    write_media_env({"S3_BUCKET": outs["MediaBucketName"], "MEDIA_BASE_URL": outs.get("MediaBaseURL", ""),
                     "AWS_REGION": region})
    print(f"\nĐã ghi S3_BUCKET={outs['MediaBucketName']} vào .env: `python run_local.py` giờ đồng bộ sản phẩm/ảnh"
          " với website trên AWS (dùng AWS credentials của máy này).")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default=os.path.join(ROOT, "deploy.env"))
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()
    load_env(a.env)
    region = os.environ.get("AWS_REGION", "ap-southeast-1")
    stack = os.environ.get("STACK_NAME", "cloudshop")
    cf = boto3.client("cloudformation", region_name=region)

    if a.status:
        link_local_env(print_outputs(cf, stack), region)
        return

    missing = [k for k in ("GitRepoUrl", "DBPassword", "AppSecretKey", "AdminPassword") if not os.environ.get(k)]
    if missing:
        sys.exit(f"Thiếu tham số trong {a.env}: {', '.join(missing)}")
    params = [{"ParameterKey": k, "ParameterValue": os.environ[k]} for k in PARAM_KEYS if os.environ.get(k) is not None]
    body = open(os.path.join(ROOT, "infra", "cloudformation.yaml"), encoding="utf-8").read()

    try:
        cf.describe_stacks(StackName=stack)
        exists = True
    except ClientError:
        exists = False

    t0 = time.time()
    try:
        if exists:
            print(f"Cập nhật stack {stack} ở {region} ...")
            cf.update_stack(StackName=stack, TemplateBody=body, Parameters=params, Capabilities=CAPS)
            waiter = cf.get_waiter("stack_update_complete")
        else:
            print(f"Tạo stack {stack} ở {region} (RDS thường mất 5–10 phút) ...")
            cf.create_stack(StackName=stack, TemplateBody=body, Parameters=params, Capabilities=CAPS,
                            Tags=[{"Key": "Project", "Value": "CloudShop"}])
            waiter = cf.get_waiter("stack_create_complete")
        waiter.wait(StackName=stack, WaiterConfig={"Delay": 20, "MaxAttempts": 120})
    except ClientError as e:
        if "No updates are to be performed" in str(e):
            print("Không có thay đổi nào.")
        else:
            raise
    except WaiterError:
        print("Stack lỗi. Xem tab Events của stack trong CloudFormation console. 10 sự kiện gần nhất:")
        for ev in cf.describe_stack_events(StackName=stack)["StackEvents"][:10]:
            print(f"  {ev['LogicalResourceId']:<26} {ev['ResourceStatus']:<22} {ev.get('ResourceStatusReason', '')}")
        sys.exit(1)
    print(f"Hoàn tất sau {int(time.time() - t0)} giây.")
    link_local_env(print_outputs(cf, stack), region)
    print("\nLưu ý: instance cần thêm 2–4 phút để cài đặt xong và vượt qua health check của ALB.")
    if exists:
        print("Stack đã có từ trước: chạy `python scripts/refresh_instances.py` để EC2 đang chạy nhận cấu hình mới.")


if __name__ == "__main__":
    main()
