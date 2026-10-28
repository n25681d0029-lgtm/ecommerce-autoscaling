# CloudShop: Website thương mại điện tử tự động co giãn (Auto Scaling) trên AWS

Demo cho đề tài *“Xây dựng và Triển khai Hệ thống Website Thương mại Điện tử Khả Trợ Năng (Auto-Scaling) trên Nền tảng Điện toán Đám mây”*.

```
Người dùng ──HTTP──► Application Load Balancer (2 AZ)
                         │  health check /health
                 ┌───────┴────────┐
              EC2 #1   EC2 #2 … EC2 #N   ◄── Auto Scaling Group (min 1, max 4)
                 └───────┬────────┘        Target Tracking: CPU trung bình 50 %
                         ▼
               Amazon RDS MySQL 8.4 (subnet riêng)
CloudWatch thu CPU / request / độ trễ  ·  SNS gửi email khi thêm/bớt instance
```

| Thư mục / file | Nội dung |
|---|---|
| `app/` | Ứng dụng Flask: cửa hàng, giỏ hàng, đặt hàng, tài khoản, trang quản trị, `/health`, `/system` |
| `run_local.py` | Chạy website trên máy cá nhân (waitress, chạy được trên Windows) |
| `wsgi.py` | Điểm vào gunicorn trên EC2 |
| `infra/cloudformation.yaml` | Toàn bộ hạ tầng AWS dưới dạng mã (VPC, ALB, ASG, RDS, CloudWatch, SNS) |
| `scripts/deploy.py`, `scripts/destroy.py` | Tạo/cập nhật và xóa stack bằng boto3 |
| `loadtest/locustfile.py` | Kịch bản kiểm thử tải (Locust) |
| `scripts/collect_metrics.py`, `plot_metrics.py`, `scaling_activities.py` | Thu số liệu thật từ CloudWatch, vẽ biểu đồ, xuất lịch sử co giãn |
| `kaggle/cloudshop_kaggle.ipynb` | Notebook chạy trên Kaggle (máy phụ) |
| `scripts/bench_local.py` | Đo năng lực một máy chủ (chỉ Linux/Kaggle), ra số liệu Mục 6.3 |
| `scripts/local_cluster.py` | Mô phỏng Load Balancer + nhiều instance ngay trên máy cá nhân, thêm/bớt instance bằng phím `+`/`-` |
| `scripts/smoke_test.py` | Kiểm tra nhanh website sau khi triển khai và đếm request mỗi instance trả lời |
| `scripts/refresh_instances.py` | Đưa code mới (sau `git push`) lên các EC2 bằng Instance Refresh, không gián đoạn website |
| `tests/` | Bộ kiểm thử tự động (pytest), chạy cả trên GitHub Actions (`.github/workflows/tests.yml`) |
| `docs/` | Kịch bản demo, hình dùng trong báo cáo, số liệu đo cục bộ gốc, `THAY_DOI.md` (nhật ký thay đổi) |

**Chức năng website:** danh mục, tìm kiếm, sắp xếp, phân trang; giỏ hàng (thêm/sửa/xóa, tự điều chỉnh theo tồn kho); đặt hàng COD có khóa dòng tồn kho; tra cứu đơn; khách tự hủy đơn khi còn “Mới” (hoàn kho); đăng ký, đăng nhập, đổi mật khẩu; trang quản trị: tổng quan + doanh thu 7 ngày + bán chạy + sắp hết hàng, quản lý sản phẩm (tìm kiếm, bổ sung kho), quản lý đơn (lọc theo trạng thái, tìm kiếm, xuất CSV, hủy đơn hoàn kho); `/health`, `/system`, `/system/live` (xem cân bằng tải theo thời gian thực).

Tài khoản quản trị website: `admin@shop.local`, mật khẩu `Admin@123` khi chạy cục bộ, hoặc `AdminPassword` bạn đặt khi triển khai lên AWS.

---

## Bước 1. Chạy thử website trên máy

### Cách A: máy chính (VS Code, Windows, PowerShell)

```powershell
cd "D:\apps\programming app\VS code\code data\ecommerce-cloud\ecommerce-autoscaling"
python -m venv py_cloudshop
.\py_cloudshop\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-tools.txt
python run_local.py
```
Mở http://127.0.0.1:8000. Dữ liệu lưu trong `instance\shop.db` (SQLite), xóa file này để làm lại từ đầu.

Nếu PowerShell chặn `Activate.ps1`: chạy `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` một lần.

**Chạy bộ kiểm thử** (dùng CSDL tạm, không đụng `instance\shop.db`):
```powershell
python -m pytest
```

**Tập dượt demo cân bằng tải không cần AWS** (mô phỏng ALB + 2 instance dùng chung CSDL và SECRET_KEY):
```powershell
python scripts\local_cluster.py --nodes 2
```
Mở http://127.0.0.1:8000/system/live, rồi gõ `+` Enter trong terminal để “scale out” (instance mới xuất hiện trong bảng sau khi qua health check), `-` để “scale in”, `s` xem trạng thái, `q` thoát. Giỏ hàng và đăng nhập vẫn giữ nguyên dù request chuyển qua instance khác. Log của từng instance nằm trong `results\cluster_logs\`.

### Cách B: máy phụ (Kaggle)

Kaggle không mở được cổng web ra ngoài, nên chỉ dùng để kiểm tra ứng dụng chạy được:
```python
!git clone -q https://github.com/<ten-github>/cloudshop.git && cd cloudshop && pip install -q -r requirements.txt
!cd cloudshop && (DISABLE_IMDS=1 gunicorn -w 2 -b 127.0.0.1:8000 wsgi:app &) && sleep 5 && curl -s 127.0.0.1:8000/health
```

---

## Bước 2. Chuẩn bị AWS (làm một lần)

1. **Đặt ngân sách cảnh báo**: Billing and Cost Management → Budgets → Create budget → *Zero spend budget* hoặc *Monthly cost budget* 5 USD, nhập email.
2. **Tạo IAM user cho nhóm** (không dùng tài khoản root): IAM → Users → Create user → gắn quyền `AdministratorAccess` (chỉ dùng cho môn học) → Security credentials → Create access key → *Command Line Interface*. Lưu Access key ID và Secret.
3. **Đưa mã nguồn lên GitHub ở chế độ Public** (EC2 sẽ `git clone` khi khởi động). Thư mục gốc repo phải chứa `wsgi.py` và `requirements.txt`.

### Cách A: máy chính (VS Code)
```powershell
winget install Amazon.AWSCLI        # hoặc tải bộ cài AWS CLI v2 từ trang AWS
aws configure                       # nhập Access key, Secret, region ap-southeast-1, output json
aws sts get-caller-identity         # kiểm tra đăng nhập
git init; git add .; git commit -m "CloudShop"; git branch -M main
git remote add origin https://github.com/<ten-github>/cloudshop.git; git push -u origin main
```

### Cách B: máy phụ (Kaggle)
Add-ons → Secrets → thêm `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`; Settings → Internet: On. Notebook `kaggle/cloudshop_kaggle.ipynb` tự đọc hai secret này.

---

## Bước 3. Triển khai hạ tầng lên AWS

### Cách A: máy chính (VS Code)
```powershell
copy deploy.env.example deploy.env    # mở deploy.env, sửa GitRepoUrl và các mật khẩu
python scripts\deploy.py              # mất khoảng 10–15 phút (RDS lâu nhất)
```
Kết thúc, script in ra `WebsiteURL` (dạng `http://cloudshop-...elb.amazonaws.com`), `LiveDemoURL` (trang `/system/live`) và `DashboardURL` (bảng điều khiển CloudWatch có sẵn biểu đồ số instance, CPU so với mục tiêu, request/phút, độ trễ p95, target khỏe/lỗi 5xx, RDS). Chờ thêm 2–4 phút để EC2 cài xong rồi kiểm tra:
```powershell
python scripts\smoke_test.py --stack cloudshop     # hoặc: python scripts\smoke_test.py http://<WebsiteURL>
```

Tùy chọn: đặt `RequestsPerTargetValue` (vd. 600) trong `deploy.env` để thêm chính sách co giãn thứ hai theo số request/phút mỗi instance; ASG sẽ chọn số instance lớn nhất mà hai chính sách đề xuất.

Muốn làm **bằng giao diện web** để chụp ảnh cho báo cáo: CloudFormation → Create stack → *Upload a template file* → chọn `infra/cloudformation.yaml` → điền tham số → Next → Submit. Kết quả giống hệt.

### Cách B: máy phụ (Kaggle)
Mở ô *(Tùy chọn) Triển khai stack từ Kaggle* trong notebook, bỏ dấu `#`, điền mật khẩu và chạy.

---

## Bước 4. Kiểm thử tải và quan sát Auto Scaling

Mở 2 cửa sổ terminal (hoặc dùng Kaggle cho việc bắn tải để máy chính rảnh tay chụp màn hình).

### Cách A: máy chính (VS Code)
```powershell
# Terminal 1: thu số liệu thật từ CloudWatch trong 35 phút
python scripts\collect_metrics.py --stack cloudshop --region ap-southeast-1 --minutes 35

# Terminal 2: bắn tải 20 phút (giao diện web của Locust ở http://localhost:8089)
locust -f loadtest\locustfile.py --host http://<WebsiteURL-khong-co-dau-/-cuoi> HeavyShopper
#   trong giao diện: Number of users = 150, Ramp up = 5, bấm Start; sau 20 phút bấm Stop
```
Sau khi Terminal 1 kết thúc:
```powershell
python scripts\plot_metrics.py results\metrics_<thoi-gian>.csv   # ra file PNG để chèn vào báo cáo
python scripts\scaling_activities.py                               # bảng thời điểm thêm/bớt instance
```

### Cách B: máy phụ (Kaggle)
Chạy các ô *Bắn tải + thu số liệu song song* trong notebook: Locust chạy headless, số liệu và biểu đồ nằm trong `/kaggle/working/cloudshop/results/` (tab Output để tải về).

Trong lúc bắn tải, mở `LiveDemoURL` và `DashboardURL` để quan sát trực tiếp. Sau khi test xong, nếu kho bị cạn (đơn không tạo được nữa), vào Quản trị → Sản phẩm → **Bổ sung kho**.

**Những gì sẽ thấy:** CPU trung bình vượt 50 % → sau vài phút Desired capacity tăng (1 → 2 → 3…) → instance mới qua health check rồi nhận tải → CPU giảm về gần 50 %. Khi dừng tải, sau một khoảng thời gian Auto Scaling giảm dần số instance về 1. Trang `/system` và chân trang website cho biết request đang do instance nào xử lý; trang Quản trị thống kê số đơn theo từng instance.

---

## Cập nhật code mới lên AWS (không cần xóa stack)

EC2 chỉ tải mã nguồn từ GitHub lúc khởi động. Sau khi sửa code: `git push`, rồi
```powershell
python scripts\refresh_instances.py           # thay lần lượt từng instance, máy mới khỏe rồi mới gỡ máy cũ
python scripts\refresh_instances.py --status  # xem tiến độ
```

---

## Bước 5. XÓA hạ tầng sau khi demo (bắt buộc để không mất tiền)

### Cách A: máy chính (VS Code)
```powershell
python scripts\destroy.py
```
### Cách B: máy phụ (Kaggle)
Bỏ dấu `#` ở ô cuối notebook: `!python scripts/destroy.py --env /dev/null --yes`

Sau đó kiểm tra EC2 → Instances, RDS → Databases, EC2 → Load Balancers đều trống.

---

## Gỡ lỗi nhanh

| Hiện tượng | Cách kiểm tra |
|---|---|
| Stack báo `ROLLBACK` | CloudFormation → stack → tab **Events**, đọc dòng `CREATE_FAILED` đầu tiên. Lỗi phiên bản MySQL: đổi `DBEngineVersion` sang bản 8.4.x đang có trong RDS console. |
| URL trả 502/503 | Instance chưa cài xong (chờ 3–4 phút) hoặc lỗi cài đặt: EC2 → chọn instance → Actions → Monitor and troubleshoot → **Get system log**, tìm dòng lỗi của `git clone`/`pip`. |
| Target group báo *unhealthy* | Mở `/health` qua URL ALB; nếu trả `db_error` thì kiểm tra mật khẩu RDS trong tham số stack. |
| Không thấy scale out | Tăng số user Locust hoặc dùng lớp `HeavyShopper`; xem tab **Activity** và **Monitoring** của Auto Scaling Group. |
| `local_cluster.py` báo cổng đang bị chiếm | Còn `run_local.py` hoặc cụm cũ đang chạy: đóng cửa sổ đó, hoặc dùng `--port 8100`. |
| Sửa code nhưng web trên AWS không đổi | Đã `git push` chưa? Sau đó chạy `python scripts\refresh_instances.py`. |
