"""Lấy thông tin máy chủ đang phục vụ request.

Trên EC2: đọc Instance Metadata Service phiên bản 2 (IMDSv2) để biết instance-id,
Availability Zone, loại instance, IP nội bộ. Ngoài AWS (chạy trên máy cá nhân)
thì trả về tên máy. Kết quả được lưu đệm vì không đổi trong suốt vòng đời instance.
"""
import os
import socket
import time
import urllib.request

_IMDS = "http://169.254.169.254/latest"
_cache: dict | None = None
STARTED_AT = time.time()


def _imds_get(path: str, token: str) -> str:
    req = urllib.request.Request(f"{_IMDS}/{path}", headers={"X-aws-ec2-metadata-token": token})
    with urllib.request.urlopen(req, timeout=0.5) as r:
        return r.read().decode()


def get_instance_info() -> dict:
    global _cache
    if _cache is not None:
        return _cache
    info = {
        "instance_id": f"local-{socket.gethostname()}",
        "availability_zone": "local",
        "instance_type": "máy cá nhân",
        "private_ip": "127.0.0.1",
        "on_aws": False,
    }
    if os.environ.get("INSTANCE_ID"):
        # Cụm mô phỏng cục bộ (scripts/local_cluster.py) đặt tên giả cho từng tiến trình
        info.update(instance_id=os.environ["INSTANCE_ID"],
                    availability_zone=os.environ.get("INSTANCE_AZ", "local"))
    elif os.environ.get("DISABLE_IMDS") != "1":
        try:
            req = urllib.request.Request(f"{_IMDS}/api/token", method="PUT",
                                         headers={"X-aws-ec2-metadata-token-ttl-seconds": "21600"})
            with urllib.request.urlopen(req, timeout=0.5) as r:
                token = r.read().decode()
            info.update(
                instance_id=_imds_get("meta-data/instance-id", token),
                availability_zone=_imds_get("meta-data/placement/availability-zone", token),
                instance_type=_imds_get("meta-data/instance-type", token),
                private_ip=_imds_get("meta-data/local-ipv4", token),
                on_aws=True,
            )
        except Exception:  # noqa: BLE001 - không ở trên EC2
            pass
    _cache = info
    return info


def uptime_seconds() -> int:
    return int(time.time() - STARTED_AT)


def load_average() -> tuple[float, float, float] | None:
    try:
        return os.getloadavg()
    except (AttributeError, OSError):  # Windows không có getloadavg
        return None
