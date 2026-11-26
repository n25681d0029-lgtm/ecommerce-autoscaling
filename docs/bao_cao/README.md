# Báo cáo và tư liệu demo

Thư mục này gom báo cáo mini project và mọi hình ảnh, ảnh chụp dùng trong báo cáo và buổi demo.

| Tệp, thư mục | Nội dung |
|---|---|
| `BaoCao_CloudShop_AutoScaling_AWS.docx` | Báo cáo (63 trang, 3 chương), mở bằng Word để chỉnh sửa |
| `BaoCao_CloudShop_AutoScaling_AWS.pdf` | Bản PDF của báo cáo để nộp hoặc chiếu |
| `anh_aws/` | 26 ảnh chụp từ lần triển khai thật trên AWS ngày 28/10/2026 (CloudFormation, EC2, Auto Scaling, ALB, RDS, CloudWatch, scale out 1 → 2 và scale in 2 → 1) |
| `anh_demo/` | Ảnh giao diện chụp ngày 25/11/2026 từ bản demo chạy trên máy cá nhân, gồm cả lúc thêm máy thứ ba và bớt máy |
| `hinh_minh_hoa/` | Sơ đồ và biểu đồ trong báo cáo: kiến trúc, cơ sở dữ liệu, luồng xử lý, kế hoạch, kết quả đo tải |
| `nguon/` | Mã dựng lại báo cáo, vẽ lại hình, chụp lại ảnh giao diện |

Kịch bản trình bày chi tiết theo từng phút nằm ở [../KICH_BAN_DEMO.md](../KICH_BAN_DEMO.md).

## Chạy demo

Các lệnh dưới đây chạy ở thư mục gốc của đồ án, trong PowerShell, sau khi kích hoạt môi trường `py_cloudshop`.

### Demo trên máy cá nhân (không cần AWS)

```powershell
.\py_cloudshop\Scripts\Activate.ps1
python scripts\local_cluster.py --nodes 2
```

- Website: http://127.0.0.1:8000
- Xem cân bằng tải trực tiếp: http://127.0.0.1:8000/system/live
- Quản trị: http://127.0.0.1:8000/admin/ (tài khoản `admin@shop.local`, mật khẩu mặc định ghi trong README của đồ án)
- Trong cửa sổ lệnh: gõ `+` rồi Enter để thêm máy, `-` để bớt máy, `s` xem trạng thái, `q` để thoát.

Kết quả mong đợi (Mục 3.3 của báo cáo, ảnh trong `anh_demo/14_live*.png`): hai máy chia đều 50/50; thêm máy thì ba máy chia đều khoảng một phần ba; giỏ hàng và đăng nhập không mất khi đổi máy.

### Demo trên AWS

1. Sao chép `deploy.env.example` thành `deploy.env`, điền địa chỉ kho GitHub, mật khẩu và đặt `AWS_REGION=ap-southeast-2` (tài khoản của nhóm chỉ dùng được vùng Sydney).
2. Tạo hệ thống trước giờ demo ít nhất 30 phút: `python scripts\deploy.py`, rồi kiểm tra: `python scripts\smoke_test.py --stack cloudshop`.
3. Mở sẵn WebsiteURL, LiveDemoURL (`/system/live`), DashboardURL ở tab Outputs và trang [Auto Scaling Groups](https://ap-southeast-2.console.aws.amazon.com/ec2/home?region=ap-southeast-2#AutoScalingGroups:).
4. Chạy tải trước lượt trình bày khoảng 10 phút: `locust -f loadtest\locustfile.py --host http://<WebsiteURL> HeavyShopper`, mở http://localhost:8089, đặt 150 người dùng, tăng 5 người mỗi giây.
5. Sau demo: `python scripts\destroy.py`, rồi kiểm tra EC2, RDS, Load Balancers không còn tài nguyên.

Kết quả mong đợi (Mục 3.4 của báo cáo, ảnh trong `anh_aws/16`–`26`): khi CPU vượt 50 %, số máy tăng từ 1 lên 2; hết tải khoảng 15 phút thì giảm về 1.

## Đối chiếu demo với báo cáo

| Phần demo | Mục trong báo cáo | Ảnh, hình |
|---|---|---|
| Kiến trúc hệ thống | 2.2.1 | `hinh_minh_hoa/f2_architecture.png` |
| Các bước tạo hệ thống trên AWS | 2.5 | `anh_aws/01`, `06`–`15` |
| Giao diện khách hàng và quản trị | 3.1 | `anh_demo/01`–`12` |
| Cân bằng tải trên máy cá nhân | 2.6.2, 3.3 | `hinh_minh_hoa/f2_local_cluster.png`, `anh_demo/14_live*.png` |
| Tăng, giảm máy trên AWS | 3.4 | `anh_aws/16`–`26`, `hinh_minh_hoa/f2_aws_timeline.png` |
| Sức chịu tải của một máy | 3.5 | `hinh_minh_hoa/f2_bench_*.png` |

## Dựng lại báo cáo

Khi sửa nội dung, sửa các tệp `nguon/content*.py` (lời văn, bảng, hình) và `nguon/content_refs.py` (tài liệu tham khảo), rồi chạy trong thư mục `docs/bao_cao`:

```powershell
pip install -r nguon\requirements.txt
python nguon\build.py BaoCao_CloudShop_AutoScaling_AWS.docx
powershell -ExecutionPolicy Bypass -File nguon\cap_nhat_muc_luc.ps1 "$PWD\BaoCao_CloudShop_AutoScaling_AWS.docx" "$PWD\BaoCao_CloudShop_AutoScaling_AWS.pdf"
```

Lệnh cuối dùng Microsoft Word để cập nhật mục lục, danh sách bảng, danh sách hình và xuất lại PDF. Nên dùng một môi trường Python riêng cho các thư viện này, không cài vào `py_cloudshop`.

Vẽ lại hình: `python nguon\figs1.py`, `python nguon\figs2.py`, rồi `python nguon\figs2_fix.py` (bản sửa của một số sơ đồ chương 2 và hình hướng phát triển).

Chụp lại ảnh giao diện: chạy demo trên máy cá nhân như ở trên, rồi `python nguon\shoot.py home,product,cart,checkout,login,admin,aprod,aform,aorders,system,live12`. Ảnh được ghi đè vào `anh_demo/`.
