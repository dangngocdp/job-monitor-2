# job-monitor-2

Bot tự động kiểm tra trang tuyển dụng mỗi ngày lúc **08:00 giờ Việt Nam**, nếu có tin tuyển dụng **mới** sẽ gửi thông báo qua **Telegram**. Chạy hoàn toàn miễn phí trên GitHub Actions, không cần bật máy tính, không gửi trùng.

Hiện đang theo dõi: **tuyendung.sungroup.com.vn**

---

## 1. Cấu trúc project

```
project/
├── monitor.py                 # Chương trình chính
├── config.json                # Danh sách website cần theo dõi
├── history.json                # Lưu vết các tin đã gửi (bot tự cập nhật)
├── requirements.txt            # Thư viện Python cần cài
└── .github/workflows/monitor.yml   # Cấu hình chạy tự động trên GitHub
```

Bạn **không cần hiểu code**. Chỉ cần làm theo các bước bên dưới.

---

## 2. Cách cập nhật project lên GitHub

**Lần này** (thay đổi nhiều file cùng lúc: `monitor.py`, `config.json`, `README.md`) → dùng cách **Upload ZIP đè lên** như hướng dẫn bên dưới.

**Từ các lần sau**, nếu chỉ cần sửa nhỏ (ví dụ: đổi tỉnh lọc, bật/tắt 1 site, sửa 1 dòng code) → làm nhanh hơn nhiều bằng cách **sửa trực tiếp trên GitHub**, không cần tải ZIP:

1. Vào file cần sửa trên GitHub (ví dụ `config.json`).
2. Bấm biểu tượng **cây bút chì ✏️** (góc phải phía trên nội dung file).
3. Sửa trực tiếp trong khung soạn thảo.
4. Cuộn xuống, bấm **Commit changes**.

Từ giờ, mỗi khi bạn nhờ tôi chỉnh sửa nhỏ, tôi sẽ nói rõ **sửa dòng nào, ở file nào, thành nội dung gì** để bạn copy-dán trực tiếp vào khung sửa trên GitHub — không cần tải lại ZIP nữa.

### Cách upload ZIP đè lên (dùng khi có nhiều file thay đổi)

1. Giải nén file ZIP ra một thư mục trên máy tính.
2. Vào repository `job-monitor-2` trên GitHub.
3. Bấm nút **Add file** (góc phải phía trên danh sách file) → chọn **Upload files**.
4. Mở thư mục vừa giải nén, **chọn hết toàn bộ file và thư mục** (kể cả thư mục `.github`), rồi **kéo thả** vào cửa sổ upload của GitHub.
   - Trình duyệt Chrome/Edge hỗ trợ kéo thả cả thư mục và giữ nguyên cấu trúc.
   - Nếu kéo thả không nhận thư mục con `.github/workflows`, bạn có thể vào từng thư mục và upload riêng file `monitor.yml` vào đúng đường dẫn `.github/workflows/monitor.yml` (tạo thư mục bằng cách gõ tên đường dẫn vào ô tên file khi upload).
5. Cuộn xuống dưới, bấm **Commit changes**.
   - GitHub sẽ tự nhận diện các file trùng tên (`monitor.py`, `README.md`, `monitor.yml`) và **ghi đè** bằng bản mới.
   - Các file mới (`config.json`, `history.json`, `requirements.txt`) sẽ được thêm vào.

**Lưu ý:** Bạn không cần tạo lại Secrets `TELEGRAM_BOT_TOKEN` và `TELEGRAM_CHAT_ID` — chúng vẫn còn nguyên vì Secrets được lưu riêng, không nằm trong code.

---

## 3. Chạy thử ngay (không cần chờ đến 8h sáng)

1. Vào tab **Actions** trên GitHub repository.
2. Bên trái chọn workflow **Website Monitor**.
3. Bấm nút **Run workflow** (góc phải) → **Run workflow** lần nữa để xác nhận.
4. Đợi khoảng 20–40 giây, bấm vào lần chạy vừa xuất hiện để xem log (nếu muốn xem chi tiết bot đã làm gì).
5. Mở Telegram — bạn sẽ nhận được 1 tin nhắn dạng:

   > ℹ️ **Sun Group**
   > Đã khởi tạo theo dõi thành công với XX tin tuyển dụng hiện có. Từ lần quét sau sẽ chỉ báo tin MỚI.

   Đây là **hành vi có chủ đích**: lần chạy đầu tiên bot sẽ ghi nhận toàn bộ tin đang có làm "mốc xuất phát", **không** gửi dồn hết XX tin về Telegram (tránh làm phiền bạn). Từ **lần chạy tiếp theo trở đi**, hễ có tin tuyển dụng mới xuất hiện, bạn sẽ nhận được tin nhắn dạng:

   > 🆕 **Tin tuyển dụng mới - Sun Group**
   >
   > **Tên vị trí tuyển dụng**
   > https://tuyendung.sungroup.com.vn/job/...

6. Kiểm tra lại repository — file `history.json` sẽ được bot **tự động commit** cập nhật danh sách ID đã gửi (bạn sẽ thấy 1 commit mới tên "Update history.json").

---

## 4. Lịch chạy tự động

Bot tự chạy **mỗi ngày lúc 08:00 giờ Việt Nam** (được cấu hình sẵn trong `monitor.yml`, không cần chỉnh gì thêm). Bạn không cần mở máy tính hay làm gì cả.

Nếu muốn đổi giờ chạy: sửa dòng `cron: '0 1 * * *'` trong file `.github/workflows/monitor.yml`. Lưu ý giờ trong GitHub Actions luôn tính theo **UTC**, giờ Việt Nam = UTC + 7.

---

## 5. Bộ lọc theo địa điểm (đã bật sẵn: Hà Nội)

Bot hiện chỉ gửi thông báo cho các tin tuyển dụng có địa điểm làm việc là **Hà Nội**. Với hầu hết các trang, địa điểm được đọc thẳng từ trang danh sách (nhanh, không tốn thêm request); riêng Sun Group phải mở thêm trang chi tiết từng tin mới để đọc địa điểm.

Tin ở tỉnh/thành khác vẫn được ghi nhận là "đã xử lý" để không quét lại, nhưng sẽ **không** gửi Telegram. Nếu bot không xác định được địa điểm của 1 tin, bot vẫn **gửi kèm cảnh báo** "không xác định được" — tránh bỏ sót tin quan trọng.

Muốn đổi/thêm địa điểm lọc cho từng site, hoặc **tắt bộ lọc để nhận tất cả tin**: mở `config.json`, sửa dòng `location_filter` của site tương ứng:

```json
"location_filter": ["Hà Nội"]              // chỉ nhận tin Hà Nội
"location_filter": ["Hà Nội", "Đà Nẵng"]   // nhận tin Hà Nội HOẶC Đà Nẵng
"location_filter": []                       // tắt lọc, nhận TẤT CẢ tin
```

⚠️ Lưu ý: **Techcombank** dùng cách viết không dấu ("Ha Noi") trên trang gốc của họ nên trong config cũng phải viết không dấu để so khớp đúng. Các site khác dùng "Hà Nội" có dấu như bình thường.

---

## 6. Danh sách website đang theo dõi

| Website | Trạng thái | Ghi chú |
|---|---|---|
| Sun Group | ✅ Hoạt động đầy đủ | Có link riêng từng tin |
| Vietcombank | ✅ Hoạt động đầy đủ | Có link riêng từng tin |
| Techcombank | ✅ Hoạt động đầy đủ | Có link riêng từng tin |
| VietinBank | ⚠️ Hoạt động có giới hạn | Trang này **không có link riêng cho từng tin** tuyển dụng (nút "Ứng tuyển" chạy bằng JavaScript). Bot vẫn phát hiện tin mới và gửi thông báo bình thường, nhưng link đính kèm trong Telegram sẽ là **link trang danh sách** (đã lọc sẵn Hà Nội) thay vì link thẳng đến tin đó. Bạn cần tự tìm tin đó trong danh sách khi bấm vào link. |
| MSB (2 mục) | ✅ Hoạt động đầy đủ | Có link riêng từng tin |
| MBBank | ⚠️ Hoạt động có giới hạn (tạm thời) | Đọc dữ liệu qua API JSON nội bộ — rất ổn định. Nhưng **hiện chưa có link thẳng đến từng tin cụ thể** (đang chờ bạn cung cấp), nên tạm thời thông báo sẽ kèm link trang danh sách chung. Sẽ tự cập nhật thành link riêng ngay khi có thông tin. |

### Cách lấy link API cho website JS-only (áp dụng cho MBBank và các site tương tự sau này)

MBBank đã được thêm thành công theo cách này. Nếu sau này có website mới cũng là dạng "ứng dụng JavaScript thuần" (tải trang xong không thấy nội dung gì), làm theo các bước sau:

1. Mở trang cần theo dõi bằng Chrome/Edge.
2. Nhấn **F12** → chọn tab **Network**.
3. Ở thanh lọc, chọn **Fetch/XHR**.
4. Nhấn **F5** để tải lại trang.
5. Trong danh sách các request hiện ra, tìm request nào có tên liên quan đến "post", "job", "search"... → bấm vào → sang tab **Preview** hoặc **Response** để xem có phải dữ liệu tin tuyển dụng không.
6. Nếu đúng, sang tab **Headers**, copy phần **Request URL** → gửi cho tôi để tôi viết parser đọc trực tiếp từ đó (nhanh và ổn định hơn nhiều so với việc giả lập trình duyệt).

### ⚠️ Lưu ý quan trọng về độ tin cậy lần cập nhật này

5 website mới (Vietcombank, Techcombank, VietinBank, MSB) được lập trình dựa trên phân tích cấu trúc trang thực tế, nhưng **chưa được chạy thử thực tế trên GitHub Actions**. Sau khi bạn upload bản này, hãy **chạy thử (Run workflow) và kiểm tra kỹ tin nhắn Telegram nhận được** ở lần chạy đầu (baseline) — nếu thấy site nào báo lỗi hoặc không tìm thấy tin nào, gửi lại log cho tôi (vào tab Actions → bấm vào lần chạy → copy log) để tôi điều chỉnh ngay.

---

## 7. Thêm website mới sau này (không cần sửa code)

Nếu website mới đó **cũng chạy trên nền tảng Base E-Hiring** (base.vn) — đây là nền tảng tuyển dụng rất phổ biến ở Việt Nam, nhiều công ty lớn dùng — bạn chỉ cần mở `config.json` và thêm 1 khối như sau:

```json
{
  "sites": [
    {
      "name": "Sun Group",
      "enabled": true,
      "type": "base_ehiring",
      "url": "https://tuyendung.sungroup.com.vn/",
      "job_url_prefix": "https://tuyendung.sungroup.com.vn/job/"
    },
    {
      "name": "Tên công ty mới",
      "enabled": true,
      "type": "base_ehiring",
      "url": "https://tuyendung.tencongtymoi.com.vn/",
      "job_url_prefix": "https://tuyendung.tencongtymoi.com.vn/job/"
    }
  ]
}
```

Cách nhận biết 1 website có dùng nền tảng Base E-Hiring hay không: cuộn xuống cuối trang, nếu thấy dòng chữ **"Powered by Base E-Hiring"** thì đúng — chỉ cần thêm config như trên là chạy được ngay, không cần sửa `monitor.py`.

Nếu website mới dùng nền tảng **khác** (không phải Base.vn), gửi lại link cho tôi (Claude), tôi sẽ viết thêm 1 phần xử lý riêng cho website đó.

---

## 8. Xử lý sự cố thường gặp

| Hiện tượng | Nguyên nhân có thể | Cách xử lý |
|---|---|---|
| Không nhận được tin nhắn Telegram nào | Secrets sai hoặc bot chưa được thêm vào chat | Kiểm tra lại `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` trong Settings → Secrets |
| Nhận được tin cảnh báo "⚠️ Không thể tải website" | Website tạm thời lỗi hoặc chặn truy cập | Thường tự hết ở lần chạy sau; nếu lặp lại nhiều ngày, báo lại cho tôi |
| Nhận được tin cảnh báo "⚠️ có thể web đã đổi giao diện" | Sun Group đổi cấu trúc trang web | Báo lại cho tôi để cập nhật lại phần đọc dữ liệu (`monitor.py`) |
| Muốn dừng theo dõi 1 website tạm thời | — | Trong `config.json`, đổi `"enabled": true` thành `"enabled": false` |

---

## 9. Bảo mật

- `TELEGRAM_BOT_TOKEN` và `TELEGRAM_CHAT_ID` **không** nằm trong code, chỉ nằm trong GitHub Secrets (đã cấu hình sẵn từ trước, không cần làm lại).
- Repository này có thể để **public** vì không có thông tin nhạy cảm nào trong code hay trong `history.json` (chỉ có số ID và tiêu đề tin tuyển dụng công khai).
