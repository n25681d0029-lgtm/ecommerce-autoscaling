# Nhật ký thay đổi

## 05/11/2026

### Chức năng mới
- **Nhiều ảnh mỗi sản phẩm** (tối đa 8):
  - Trang quản trị: tải nhiều ảnh cùng lúc, xem trước, chọn ảnh chính, xóa từng ảnh.
  - Trang chi tiết có thư viện ảnh (bấm ảnh nhỏ để đổi ảnh lớn).
  - Ảnh chính hiện ở trang chủ, giỏ hàng và danh sách quản trị.
  - Sản phẩm chưa có ảnh vẫn dùng ảnh minh họa SVG.
- Ảnh tải lên được kiểm tra bằng Pillow: từ chối file giả đuôi ảnh và "bom giải nén". Ảnh được xoay theo EXIF, thu nhỏ còn cạnh dài ≤ 1000 px, nén lại thành JPEG và bỏ siêu dữ liệu (GPS...). File quá 5 MB trả trang lỗi 413.
- **Xóa sản phẩm** (xóa mềm):
  - Sản phẩm biến mất khỏi cửa hàng, trang quản trị và giỏ hàng.
  - Đơn hàng cũ giữ nguyên.
  - SKU được giải phóng để dùng lại.
- **Đồng bộ sản phẩm giữa các máy** (xem [DONG_BO_SAN_PHAM.md](DONG_BO_SAN_PHAM.md)):
  - Sản phẩm và ảnh nằm ở một kho chung: S3 khi có AWS, thư mục `catalog/` trong repo khi không có.
  - Mọi máy (EC2, `run_local.py`) tự gộp với kho này lúc khởi động, sau mỗi lần sửa và mỗi 30 giây. Bản sửa mới nhất thắng.
  - Trang Quản trị → Sản phẩm hiển thị trạng thái đồng bộ và có nút **Đồng bộ ngay**.

### Hạ tầng (CloudFormation)
- Thêm `MediaBucket` (S3, chặn truy cập công khai, mã hóa), `MediaDistribution` (CloudFront + Origin Access Control: chỉ CloudFront đọc được thư mục `images/`) và `MediaBucketPolicy`.
- Thêm `AppRole` + `AppInstanceProfile`: EC2 được đọc/ghi đúng bucket này, không cần access key trên máy chủ. Vì có IAM role, `deploy.py` gửi kèm `CAPABILITY_IAM`.
- Output mới: `MediaBucketName`, `MediaBaseURL`. `cfn-lint`: chỉ còn cảnh báo W1011 có từ trước.

### Công cụ
- `deploy.py` (cả `--status`) tự ghi `S3_BUCKET`, `MEDIA_BASE_URL`, `AWS_REGION` vào `.env` để `run_local.py` dùng chung kho với AWS.
- `destroy.py` sao lưu catalog + ảnh từ S3 về `catalog/`, làm trống bucket rồi mới xóa stack, sau đó gỡ các dòng S3 khỏi `.env`.
- Kiểm thử: `tests/test_images.py` (6), `tests/test_catalog_sync.py` (7, gồm S3 giả lập và trường hợp hai máy ghi cùng lúc). Tổng cộng 51 kiểm thử.

### Lưu ý tương thích
- Thêm thư viện `Pillow`, `boto3` vào `requirements.txt`.
- CSDL cũ (`instance/shop.db`, RDS) **tự nâng cấp** khi khởi động:
  - Bảng `products` có thêm cột `uid`, `updated_at`, `deleted_at`.
  - Bảng mới `product_photos`.
  - Ảnh của bản thử nghiệm trước (bảng `product_images`) được chuyển sang kho ảnh rồi bảng đó bị xóa.
- Stack đang chạy: `python scripts\deploy.py` (cập nhật stack) rồi `python scripts\refresh_instances.py`.
- **Chưa chạy thử trên AWS thật.** S3/CloudFront/IAM mới chỉ kiểm tra bằng `cfn-lint` và S3 giả lập trong kiểm thử. Nên triển khai thử một lần trước buổi demo.

## 22/10/2026

### Sửa lỗi
- Tham số không hợp lệ trên URL/form (`/?page=abc`, số lượng giỏ là chữ, `/api/heavy?ms=x`) trước đây gây lỗi 500, giờ dùng giá trị mặc định.
- Đăng nhập: chặn chuyển hướng ra trang ngoài qua `?next=//evil.com` (open redirect).
- Giỏ hàng / đặt hàng:
  - Sản phẩm hết hàng vẫn thêm được vào giỏ với số lượng 0 và tạo ra đơn 0 đ: nay bị chặn.
  - Sản phẩm đã ẩn (ngừng bán) vẫn đặt được: nay bị loại khỏi giỏ kèm thông báo.
  - Số lượng trong giỏ tự giảm theo tồn kho thực tế.
- Đặt hàng: kiểm tra định dạng số điện thoại và độ dài họ tên/địa chỉ (MySQL strict mode sẽ báo lỗi 500 nếu chuỗi dài hơn cột).
- Quản trị sản phẩm: trùng SKU, giá/tồn âm, danh mục không tồn tại, màu ngoài 0–359 trước đây gây lỗi 500 hoặc lưu dữ liệu sai; nay báo lỗi và giữ lại dữ liệu đã nhập.
- Hủy đơn không hoàn lại tồn kho: nay hoàn kho (có khóa dòng như lúc đặt hàng); đơn đã hủy không mở lại được để tránh trừ kho hai lần.
- `run_local.py` bị crash (`UnicodeEncodeError`) khi output bị chuyển hướng ra file trên Windows có code page khác UTF-8 (vd. `python run_local.py > log.txt`).
- Sản phẩm liên quan trên trang chi tiết không còn hiện sản phẩm đã ẩn.

### Chức năng mới
- Khách: xóa từng sản phẩm trong giỏ; tự hủy đơn khi đơn còn “Mới” (chủ tài khoản, hoặc khách vãng lai trên cùng trình duyệt đã đặt); trang Tài khoản và đổi mật khẩu.
- Quản trị: doanh thu 7 ngày (biểu đồ cột), top 5 bán chạy, danh sách sắp hết hàng; tìm sản phẩm theo tên/SKU; nút “Bổ sung kho” (tiện khi kiểm thử tải làm cạn kho); lọc đơn theo trạng thái (có đếm số đơn) và tìm theo mã đơn/SĐT/tên; xuất CSV đơn hàng (mở được bằng Excel).
- Trang lỗi 403/404/500 thân thiện, có hiển thị instance đang phục vụ.
- `/system/live`: trang xem cân bằng tải theo thời gian thực (số request mỗi instance trả lời, instance mới xuất hiện khi scale out).
- Menu quản trị gộp vào `templates/admin/_nav.html`.

### Hạ tầng (CloudFormation)
- `MonitoringDashboard`: bảng điều khiển CloudWatch tạo sẵn cùng stack; output mới `DashboardURL`, `LiveDemoURL`.
- Tham số `RequestsPerTargetValue` (mặc định 0 = tắt): chính sách Target Tracking thứ hai theo `ALBRequestCountPerTarget`.
- Template đã kiểm tra bằng `cfn-lint`: chỉ còn cảnh báo W1011 có từ trước (khuyên dùng Secrets Manager cho mật khẩu RDS, phù hợp làm “hướng phát triển”).

### Công cụ
- `tests/`: 38 kiểm thử pytest (cửa hàng, tài khoản, quản trị, hệ thống); `.github/workflows/tests.yml` chạy tự động trên GitHub.
- `scripts/local_cluster.py`: mô phỏng ALB + nhiều instance trên máy cá nhân, thêm/bớt instance khi đang chạy.
- `scripts/smoke_test.py`: kiểm tra website sau triển khai và đếm phân bổ request.
- `scripts/refresh_instances.py`: cập nhật code mới lên EC2 bằng Instance Refresh.

### Lưu ý tương thích
- Không thay đổi cấu trúc bảng CSDL: `instance/shop.db` cũ và RDS hiện có dùng tiếp được.
- `refresh_instances.py`, dashboard và chính sách theo request **chưa chạy thử trên AWS thật** (chỉ kiểm tra cú pháp, `cfn-lint` và JSON của dashboard); nên thử một lần trước buổi demo.
