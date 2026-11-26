#!/usr/bin/env bash
# Cài đặt và chạy demo trên Linux/macOS:  bash cai_dat_va_chay.sh        (demo cân bằng tải)
#                                         bash cai_dat_va_chay.sh web    (chỉ chạy website)
#                                         bash cai_dat_va_chay.sh test   (chạy bộ kiểm thử)
set -e
cd "$(dirname "$0")"
PY=${PYTHON:-python3}
"$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' || { echo "Cần Python 3.10 trở lên"; exit 1; }
if [ ! -x .venv/bin/python ]; then
  "$PY" -m venv .venv
  .venv/bin/python -m pip install --upgrade pip
  .venv/bin/python -m pip install -r requirements.txt
  .venv/bin/python -m pip install -r requirements-tools.txt || echo "Cảnh báo: chưa cài được công cụ kiểm thử"
fi
case "${1:-demo}" in
  web)  .venv/bin/python run_local.py ;;
  test) .venv/bin/python -m pytest ;;
  *)    echo "Mở http://127.0.0.1:8000/system/live — gõ + / - rồi Enter để thêm/bớt máy, q để thoát"
        .venv/bin/python scripts/local_cluster.py --nodes 2 ;;
esac
