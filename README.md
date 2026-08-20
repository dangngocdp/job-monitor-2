# job-monitor-2

Bot tự động kiểm tra trang tuyển dụng mỗi ngày lúc **08:00 giờ Việt Nam**, nếu có tin tuyển dụng **mới tại Hà Nội** sẽ gửi thông báo qua **Telegram**. Chạy hoàn toàn miễn phí trên GitHub Actions, không cần bật máy tính, không gửi trùng.

---

## ⚠️ LƯU Ý QUAN TRỌNG CHO LẦN CẬP NHẬT NÀY

Lần này bạn **CHỈ upload đè 4 file sau**, **KHÔNG upload `history.json`**:

- `monitor.py`
- `config.json`
- `README.md`
- `.github/workflows/monitor.yml`

Lý do: file `history.json` đang có trên GitHub của bạn đã lưu lịch sử các tin đã gửi cho 10 site cũ. Nếu ghi đè bằng file `history.json` rỗng đi kèm ZIP này, các site cũ sẽ chạy lại "lần đầu tiên" (gửi lại tin "đã khởi tạo theo dõi" — không hại gì nghiêm trọng, nhưng không cần thiết). Bỏ qua file này khi upload, hệ thống sẽ tự thêm dữ liệu cho 3 site mới vào đúng file `history.json` đang có.

---

## Danh sách 13 mục đang theo dõi

| # | Tên | Trạng thái |
|---|---|---|
| 1 | Sun Group | ✅ |
| 2 | Vietcombank | ✅ |
| 3 | Techcombank | ✅ |
| 4 | VietinBank (trực tiếp) | ⏸️ Tắt — chưa tìm được đúng API |
| 5 | **VietinBank (qua VietnamWorks)** | 🆕 Mới thêm — độ tin cậy **trung bình** (xem lưu ý bên dưới) |
| 6 | SHB | ✅ |
| 7 | MSB - NHTM và tiêu dùng | ✅ |
| 8 | MSB - Hành chính Văn thư Thư ký | ✅ |
| 9 | MBBank | ✅ |
| 10 | TPBank | ✅ |
| 11 | SunPhuQuoc Airways | ✅ |
| 12 | **LPBank** | 🆕 Mới thêm — độ tin cậy cao (cùng nền tảng TPBank) |
| 13 | **BIDV** | 🆕 Mới thêm — độ tin cậy cao (đã test bằng dữ liệu thật) |

### Lưu ý về 3 site mới

- **LPBank**: dùng lại đúng công nghệ đã hoạt động ổn định với TPBank/SunPhuQuoc Airways → độ tin cậy cao.
- **BIDV**: đã test kỹ với dữ liệu thật bạn cung cấp. Có 1 giới hạn: **không có link riêng từng tin** (dữ liệu API không kèm link) → thông báo sẽ đính kèm link trang danh sách chung thay vì link thẳng tới tin.
- **VietinBank (qua VietnamWorks)**: đây là phương án thay thế vì không tìm được API chính thức của trang VietinBank. Cách đọc dữ liệu dựa trên cấu trúc trang mà tôi quan sát được nhưng **chưa qua kiểm thử với dữ liệu thật 100%** — cần theo dõi kỹ lần chạy đầu, nếu có vấn đề (báo lỗi hoặc không tìm thấy tin) hãy gửi lại log để điều chỉnh.

---

## Cách chạy thử

1. Vào tab **Actions** trên GitHub → chọn **Website Monitor** → **Run workflow**.
2. Đợi 20-60 giây (nhiều site hơn nên hơi lâu hơn trước).
3. Kiểm tra Telegram — các site MỚI (LPBank, BIDV, VietinBank qua VietnamWorks) sẽ gửi tin "đã khởi tạo theo dõi" (bình thường, không phải lỗi). Các site cũ sẽ im lặng nếu không có tin mới (vì đã có lịch sử từ trước, không bị reset).
4. Nếu site nào báo lỗi/0 tin, vào tab Actions xem log, copy gửi lại cho tôi.

## Cấu hình lọc địa điểm

Mỗi site có `location_filter` riêng trong `config.json`, mặc định `["Hà Nội"]`. Đổi thành `[]` để tắt lọc (nhận mọi địa điểm), hoặc thêm tỉnh khác vào mảng.

## Sửa nhanh không cần ZIP

Với các thay đổi nhỏ (đổi địa điểm lọc, bật/tắt 1 site...), vào file trên GitHub → bấm ✏️ → sửa → **Commit changes**, không cần tải lại ZIP.
