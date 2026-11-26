# Đồng bộ sản phẩm và ảnh giữa các máy

## Vấn đề

Mỗi nơi chạy website có CSDL riêng:

- `python run_local.py` dùng SQLite `instance/shop.db`. File này không đưa lên git.
- Website trên AWS dùng RDS MySQL, nằm trong mạng riêng của stack.

Vì vậy nếu chỉ lưu vào CSDL, sản phẩm thêm/sửa/xóa ở máy này không hiện ở máy khác. Ảnh cũng vậy: lưu trên ổ đĩa của một EC2 thì các EC2 khác sau Load Balancer không thấy ảnh, và ảnh mất khi Auto Scaling xóa máy đó.

## Giải pháp: một "kho catalog" dùng chung

```
            catalog.json + images/<mã băm>.jpg
        ┌──────────── kho catalog dùng chung ────────────┐
        │  S3 bucket (khi có stack AWS)                  │
        │  hoặc thư mục catalog/ trong repo (đi theo git) │
        └───────▲──────────────▲──────────────▲──────────┘
       gộp 2 chiều       gộp 2 chiều     gộp 2 chiều
        ┌───────┴───┐   ┌──────┴─────┐   ┌────┴────────┐
        │ EC2 #1    │   │ EC2 #2 ... │   │ run_local.py│
        │ (RDS)     │   │ (RDS)      │   │ (SQLite)    │
        └───────────┘   └────────────┘   └─────────────┘
```

- **Ảnh** được lưu một lần vào kho, đặt tên theo mã băm nội dung. Trên AWS, trình duyệt tải ảnh thẳng từ **CloudFront**, không đi qua EC2. Khi chạy local, Flask phục vụ ảnh qua `/media/<tên file>`.
- **Danh mục sản phẩm** (`catalog.json`): mỗi máy gộp CSDL của mình với file này vào các lúc sau:
  - khi khởi động;
  - ngay sau mỗi lần quản trị viên lưu, xóa hoặc bổ sung kho;
  - khi bấm nút **Đồng bộ ngay**;
  - tự động mỗi 30 giây (`SYNC_INTERVAL`).
- **Quy tắc gộp:** mỗi sản phẩm có `uid` cố định và thời điểm sửa cuối `updated_at`. Bản sửa **mới nhất thắng**. Sản phẩm bị xóa để lại "bia mộ" (`deleted: true`) để máy khác xóa theo, không tạo lại sản phẩm từ bản cũ.
- **Hai máy ghi cùng lúc:** trên S3, việc ghi `catalog.json` dùng *ghi có điều kiện* (`If-Match`). Nếu máy khác vừa ghi trước, S3 từ chối, và máy này đọc lại rồi gộp lại, nên không mất thay đổi của ai.

## Dùng thế nào

### 1. Chỉ chạy local, nhiều máy (không có AWS)

```powershell
python run_local.py                 # sửa sản phẩm, upload ảnh trong trang Quản trị
git add catalog
git commit -m "Cập nhật sản phẩm"
git push
```
Trên máy kia, chạy `git pull` rồi `python run_local.py`: sản phẩm và ảnh giống hệt máy trước.

### 2. Có stack AWS

`python scripts\deploy.py` tạo bucket S3 + CloudFront, rồi **tự ghi** 3 dòng `S3_BUCKET`, `MEDIA_BASE_URL`, `AWS_REGION` vào `.env` của máy đó. Từ đó:

- `run_local.py` trên máy này đọc và ghi thẳng S3. Sửa ở local thì website AWS thấy sau tối đa khoảng 30 giây, và ngược lại.
- Mọi thay đổi vẫn được chép thêm một bản vào `catalog/` để bạn commit lên git.
- Máy khác có AWS credentials: chạy `python scripts\deploy.py --status` một lần để ghi `.env` rồi chạy `run_local.py`.
- Máy không có AWS credentials vẫn dùng cách 1 (git).
- Lần đầu bucket còn trống, EC2 lấy dữ liệu ban đầu từ thư mục `catalog/` trong mã nguồn (đã `git clone`) và đẩy lên S3.

### 3. Xóa stack

`python scripts\destroy.py` **tải toàn bộ catalog và ảnh từ S3 về `catalog/`**, làm trống bucket, xóa stack, rồi gỡ 3 dòng S3 khỏi `.env`. Bạn commit `catalog/` lên git. Lần `deploy.py` sau, website mới có lại đúng các sản phẩm đó.

## Những gì không đồng bộ

| Dữ liệu | Lý do |
|---|---|
| Đơn hàng, tài khoản khách | Dữ liệu giao dịch, mỗi môi trường giữ riêng (đơn kiểm thử tải trên AWS không lẫn vào máy cá nhân). |
| Tồn kho bị trừ khi khách đặt hàng | Đặt hàng không đổi `updated_at`, nên không ghi đè tồn kho nơi khác. Tồn kho chỉ đồng bộ khi quản trị viên **sửa sản phẩm** hoặc bấm **Bổ sung kho**. |

## Biến môi trường

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `S3_BUCKET` | (trống) | Có giá trị thì dùng S3 làm kho chung; trống thì dùng thư mục `catalog/` |
| `MEDIA_BASE_URL` | (trống) | Địa chỉ CloudFront; trống thì ảnh S3 được phát qua Flask (`/media/...`) |
| `AWS_REGION` | | Region của bucket |
| `CATALOG_DIR` | `catalog/` | Thư mục kho local / bản sao |
| `CATALOG_MIRROR` | `1` | Khi dùng S3, chép thêm bản sao vào `CATALOG_DIR`. Trên EC2 đặt `0` |
| `SYNC_INTERVAL` | `30` | Số giây giữa các lần tự đồng bộ; `0` thì tắt đồng bộ nền |

## Giới hạn đã biết

- Hai người sửa **cùng một sản phẩm** gần như cùng lúc ở hai máy: bản lưu sau cùng thắng cả sản phẩm, không trộn từng trường. Đồng hồ các máy cần đúng giờ (Windows/EC2 tự đồng bộ giờ qua Internet).
- Hai máy cùng tạo **hai sản phẩm khác nhau nhưng trùng SKU** trước khi kịp đồng bộ: máy nhận sẽ bỏ qua bản trùng và ghi cảnh báo trong log. Đổi SKU một trong hai sản phẩm là xong.
- Ảnh trên S3 không bị xóa khi sản phẩm bị xóa (dung lượng rất nhỏ). Ảnh không còn dùng trong thư mục `catalog/` được tự dọn sau 1 giờ.
