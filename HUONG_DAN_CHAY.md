# Hướng dẫn chạy CloudShop trên máy khác

## Yêu cầu

- Python 3.10 trở lên (khuyên dùng 3.11): https://www.python.org/downloads/ — khi cài trên Windows nhớ tick **Add python.exe to PATH**.
- Có Internet ở lần cài đặt đầu tiên (để tải thư viện). Sau đó chạy demo không cần Internet.
- Không cần MySQL hay AWS: khi chạy trên máy, website tự dùng SQLite và tự tạo 36 sản phẩm mẫu.

## Windows

1. Giải nén file zip ra một thư mục bất kỳ.
2. Bấm đúp **`CAI_DAT.bat`** (chỉ làm một lần, mất vài phút).
3. Chọn một trong các cách chạy:

| Tệp | Việc làm |
|---|---|
| `CHAY_DEMO.bat` | Demo cân bằng tải: 2 máy chủ giả lập sau một bộ cân bằng tải, tự mở http://127.0.0.1:8000/system/live. Trong cửa sổ đen gõ `+` rồi Enter để thêm máy, `-` để bớt máy, `q` để thoát |
| `CHAY_WEB.bat` | Chạy website một máy chủ tại http://127.0.0.1:8000 |
| `CHAY_KIEM_THU.bat` | Chạy 62 bài kiểm thử tự động |

## Linux / macOS

```bash
bash cai_dat_va_chay.sh        # cài (lần đầu) rồi chạy demo cân bằng tải
bash cai_dat_va_chay.sh web    # chỉ chạy website
bash cai_dat_va_chay.sh test   # chạy bộ kiểm thử
```

## Tài khoản quản trị

Email `admin@shop.local`, mật khẩu mặc định ghi ở mục “Tài khoản quản trị website” trong `README.md`. Trang quản trị: http://127.0.0.1:8000/admin/

## Gỡ lỗi nhanh

| Hiện tượng | Cách xử lý |
|---|---|
| “Không tìm thấy Python” | Cài Python, tick “Add python.exe to PATH”, mở lại máy hoặc cửa sổ lệnh |
| Cài thư viện thất bại | Kiểm tra Internet rồi chạy lại `CAI_DAT.bat` |
| Báo cổng 8000 đang bị chiếm | Tắt cửa sổ website/demo đang chạy trước đó rồi chạy lại |
| Muốn làm lại dữ liệu từ đầu | Xóa thư mục `instance` rồi chạy lại |

## Có gì trong gói

- Mã nguồn website (`app/`, `run_local.py`, `wsgi.py`), hạ tầng AWS (`infra/`), công cụ (`scripts/`), kiểm thử (`tests/`, `loadtest/`), danh mục sản phẩm và ảnh (`catalog/`).
- Báo cáo và tư liệu demo trong `docs/bao_cao/` (Word, PDF, ảnh chụp AWS, ảnh giao diện, sơ đồ). Xem `docs/bao_cao/README.md`.
- Triển khai lên AWS: xem Bước 2–5 trong `README.md` (cần tài khoản AWS và tạo `deploy.env` từ `deploy.env.example`).
