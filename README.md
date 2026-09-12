# job-monitor-2

Bot tự động kiểm tra trang tuyển dụng mỗi ngày lúc **08:00 giờ Việt Nam**, gửi thông báo qua **Telegram** khi có tin mới phù hợp bộ lọc địa điểm.

---

## ⚠️ LƯU Ý QUAN TRỌNG CHO LẦN CẬP NHẬT NÀY

Chỉ upload đè **3 file**: `monitor.py`, `config.json`, `README.md`.
**KHÔNG upload `history.json`** — file đang có trên GitHub đã lưu lịch sử các site cũ, ghi đè sẽ khiến các site đó chạy lại "lần đầu" không cần thiết (không hại gì nghiêm trọng, chỉ gửi lại tin "đã khởi tạo theo dõi").

`.github/workflows/monitor.yml` **không thay đổi** so với bản đang chạy — không cần upload lại.

---

## 🔧 Đã sửa lỗi quan trọng: SHB đọc sai địa điểm

Phát hiện khi phân tích PVcomBank (cùng nền tảng với SHB): trang tin tuyển dụng hiển thị địa điểm dạng **chữ trần** (chỉ "Hà Nội"), không có nhãn "Nơi làm việc:" như giả định ban đầu khi viết code cho SHB. Điều này khiến SHB **trước đây có thể đã không lọc đúng địa điểm** — mọi tin mới đều bị gửi kèm cảnh báo "không xác định được". Đã sửa để đọc đúng cả 2 kiểu (có nhãn và không có nhãn).

---

## Danh sách 18 mục đang theo dõi

| # | Tên | Trạng thái |
|---|---|---|
| 1-14 | Sun Group, Vietcombank, Techcombank, MSB×2, MBBank, TPBank, SunPhuQuoc Airways, LPBank, BIDV, SHB (đã vá lỗi) | ✅ Đã chạy ổn định trước đó |
| 15 | VietinBank (trực tiếp) | ⏸️ Tắt — chưa tìm được đúng API |
| 16 | **VPBank** | 🆕 Độ tin cậy cao (cùng nền tảng Vietcombank/Techcombank) |
| 17 | **VietinBank (qua VietnamWorks)** | 🆕 Độ tin cậy trung bình — cần theo dõi lần chạy đầu |
| 18 | **NCB (qua VietnamWorks)** | 🆕 Độ tin cậy trung bình — cần theo dõi lần chạy đầu |
| 19 | **PVcomBank** | 🆕 Độ tin cậy cao (đã test bằng dữ liệu thật) |
| 20 | **BacA Bank** | 🆕 Độ tin cậy trung bình — trang chặn robots.txt nên chưa xem trực tiếp được dữ liệu, chỉ suy ra từ tìm kiếm |
| 21 | **SeABank** | 🆕 Độ tin cậy cao (đã test bằng dữ liệu thật, URL tự lọc sẵn Hà Nội) |

*(Số thứ tự không phản ánh đúng 18 dòng thực tế trong config do gộp nhóm mô tả — xem file `config.json` để có danh sách chính xác.)*

---

## Cách chạy thử

1. Tab **Actions** → **Website Monitor** → **Run workflow**.
2. Đợi 30-90 giây (18 site nên lâu hơn trước khá nhiều).
3. Các site MỚI sẽ gửi tin "đã khởi tạo theo dõi" — bình thường. Site cũ im lặng nếu không có tin mới (lịch sử không bị mất).
4. Nếu site nào lỗi/0 tin, xem log trong tab Actions và gửi lại cho tôi.

## Bộ lọc nâng cao: Địa điểm + Phòng ban (dùng cho VietABank sau này)

Ngoài `location_filter` (mặc định so khớp kiểu "chỉ cần 1 từ khóa đúng"), có thể thêm `"location_filter_mode": "all"` để bắt buộc **tất cả** từ khóa phải cùng xuất hiện — ví dụ vừa đúng địa điểm vừa đúng phòng ban.

## Sửa nhanh không cần ZIP

Thay đổi nhỏ (đổi địa điểm lọc, bật/tắt site...): vào file trên GitHub → ✏️ → sửa → **Commit changes**.
