# Kịch bản demo (khoảng 12–15 phút)

Chuẩn bị trước buổi demo **ít nhất 30 phút**: chạy `python scripts/deploy.py`, mở sẵn các tab trình duyệt dưới đây, chạy `python scripts/smoke_test.py --stack cloudshop` để chắc chắn mọi trang đều OK. Ghi sẵn ảnh chụp và biểu đồ của lần chạy thử trước, phòng khi mạng chậm.

## 1. Nêu bài toán (1–2 phút)
- **Input**: request của khách (xem, tìm, giỏ hàng, đặt hàng) có lưu lượng thay đổi; tham số co giãn (min 1, max 4, CPU mục tiêu 50 %); số liệu CloudWatch.
- **Output**: trang web phản hồi ổn định; đơn hàng lưu trong RDS; số máy chủ tự thay đổi; email thông báo; biểu đồ giám sát.
- **Hướng giải quyết**: ứng dụng phi trạng thái + CSDL dùng chung + ALB + Auto Scaling Target Tracking. Mở Hình 1.1 (kiến trúc).

## 2. Các bước triển khai lên AWS (4–5 phút)
1. CloudFormation → stack `cloudshop` → tab **Template**: chỉ nhanh các khối VPC, ALB, LaunchTemplate (user data), AutoScalingGroup, ScalingPolicy, Database.
2. Tab **Parameters** → tab **Events** (CREATE_COMPLETE) → tab **Outputs** (WebsiteURL).
3. EC2 → **Launch Templates**: AMI Amazon Linux 2023, t3.micro, user data.
4. EC2 → **Target Groups** → Targets: healthy, health check `/health`.
5. EC2 → **Auto Scaling Groups** → Details (1/1/4) → Automatic scaling (Target tracking CPU 50).
6. RDS → Databases: MySQL 8.4, không truy cập công khai. Security Groups: chuỗi ALB → App → DB.

## 3. Giao diện và chức năng (3 phút)
Trang chủ → lọc danh mục, tìm kiếm → chi tiết → thêm giỏ → đặt hàng → mã đơn (có nút tự hủy đơn) → tra cứu đơn → đăng nhập admin → tổng quan (doanh thu 7 ngày, bán chạy), sửa sản phẩm, lọc đơn theo trạng thái, đổi trạng thái / hủy đơn (tồn kho được hoàn lại), xuất CSV → trang `/system`.

## 4. Demo Auto Scaling (3–4 phút, chạy tải từ trước 10 phút)
- Bắn tải bằng Locust (máy chính) hoặc notebook Kaggle (máy phụ) **trước khi đến lượt trình bày khoảng 10 phút** vì scale out mất vài phút.
- Cho xem: Locust (RPS, số user) → ASG tab **Activity** (dòng "Launching a new EC2 instance … changing the desired capacity from 1 to 2") → tab **Monitoring** (CPU) → EC2 Instances (thêm máy mới) → F5 trang `/system` thấy instance ID thay đổi → trang Quản trị: số đơn theo máy chủ.
- **Mở sẵn trang `/system/live`** (output `LiveDemoURL`) từ lúc bắt đầu bắn tải: khi ASG thêm máy, một dòng instance mới tự xuất hiện và tỉ lệ request chia đều ra; dải màu “50 request gần nhất” cho thấy ALB luân phiên giữa các máy. Đây là hình ảnh trực quan nhất cho người nghe.
- **Bảng điều khiển CloudWatch** (output `DashboardURL`): một màn hình có đủ số instance (InService/Desired), CPU so với đường mục tiêu 50 %, request/phút, độ trễ p95, target khỏe và lỗi 5xx. Chụp màn hình này cho báo cáo.
- Phương án dự phòng khi mạng/AWS có sự cố: chạy `python scripts\local_cluster.py` trên máy, mở http://127.0.0.1:8000/system/live, gõ `+` / `-` để minh họa scale out / scale in.
- Dừng tải, nói: sau một khoảng thời gian ASG tự giảm về 1 (có thể chiếu biểu đồ của lần chạy thử trước).

## 5. Kết luận và hướng phát triển (1 phút)
HTTPS (ACM + Route 53), Secrets Manager, RDS Multi-AZ, ElastiCache, CloudFront + S3, CI/CD, ECS Fargate.

**Sau demo: `python scripts/destroy.py`.**
