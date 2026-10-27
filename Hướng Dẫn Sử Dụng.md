# Hướng Dẫn Sử Dụng Chatbot Gợi Ý & Đặt Đồ Uống (Discord Bot)

Hệ thống Chatbot AI gợi ý đồ uống thông minh theo tâm trạng, thời tiết và khẩu vị tự nhiên, hỗ trợ chọn món và đặt hàng trực quan ngay trên **Discord**.

---

## 1. Kiến Trúc & Công Nghệ Cốt Lõi

- **Bộ Máy Gợi Ý Lai (Hybrid Recommendation Engine)**:
  - **Tầng 1 - Semantic Vector Search**: Sử dụng mô hình nhúng đa ngôn ngữ `paraphrase-multilingual-MiniLM-L12-v2` tăng tốc phần cứng bằng **NVIDIA GeForce RTX 4080 (CUDA)**.
  - **Tầng 2 - Rule-based Intent Matching**: Tự động nhận diện ý định về nhiệt độ (nóng/đá), hàm lượng calo/healthy, caffeine (tỉnh táo vs không mất ngủ), vị giác (chua, béo, đắng, the mát) và ngân sách.
  - **Điểm kết hợp (Hybrid Score)**: Phối hợp $60\%$ Vector Similarity và $40\%$ Intent Matching, tự động sinh lý do giải thích trực quan: *"Vì sao món này sinh ra cho bạn?"*.
  - **Dự phòng (Graceful Degradation)**: Tích hợp bộ TF-IDF N-gram Vectorizer nội bộ thuần Python, đảm bảo bot vẫn hoạt động chính xác ngay cả khi ngoại tuyến.
- **Cơ Sở Dữ Liệu SQLite (`Cơ Sở Dữ Liệu Đồ Uống.db`)**:
  - `DoUong`: Quản lý danh mục 20+ món chọn lọc (Cà phê, Trà sữa, Trà hoa quả, Đá xay, Nước ép, Thư giãn dưỡng sinh).
  - `GioHang`: Lưu giỏ hàng, tùy chỉnh size (M/L), mức đường, mức đá, topping và số lượng.
  - `SoThichNguoiDung`: Ghi nhớ khẩu vị và món yêu thích riêng của từng Discord User.
- **Giao Diện Discord Rich UI**:
  - Tận dụng `discord.py v2` với Slash Commands (`/`), Discord Embeds tông màu thẩm mỹ, Button tương tác, Dropdown Select Menu và Modal điền form đặt nước.

---

## 2. Cấu Trúc Thư Mục Chuẩn Universal (sep=" ")

```text
d:\Project\Chatbot For Ordering Drinks\
│
├── Dữ Liệu Menu.json            # Bộ dữ liệu 20 món đồ uống kèm metadata calo, vị giác, tâm trạng
├── Cơ Sở Dữ Liệu.py             # Quản lý SQLite database (Menu, Giỏ hàng, Sở thích cá nhân)
├── Cơ Sở Dữ Liệu Đồ Uống.db     # File SQLite Database tự động tạo và đồng bộ
├── Bộ Máy Gợi Ý.py              # Engine Semantic Search + Rule Intent + CUDA RTX 4080
├── Khởi Chạy Bot.py             # Điểm vào chính của Discord Bot (Slash Commands, Buttons, Modals)
├── Mẫu Cấu Hình.env             # File hướng dẫn cấu hình biến môi trường
├── .env                         # Nơi lưu DISCORD_BOT_TOKEN thực tế
└── Hướng Dẫn Sử Dụng.md         # Tài liệu hướng dẫn sử dụng chi tiết
```

---

## 3. Hệ Thống Lệnh Discord (Slash Commands)

| Lệnh | Tham số | Mô tả tính năng |
| :--- | :--- | :--- |
| **`/goi-y`** | `mo_ta` *(bắt buộc)*<br>`danh_muc` *(tùy chọn)* | Gợi ý món thông minh theo cảm xúc, thời tiết, khẩu vị tự nhiên. Trả về Embed chi tiết kèm nút **[🥤 Đặt món này ngay]**, **[🎲 Gợi ý tiếp theo]**, **[❤️ Lưu yêu thích]**. |
| **`/menu`** | *Không* | Xem toàn bộ menu đồ uống với Dropdown Select Menu chọn lọc nhanh từng danh mục. |
| **`/tim-mon`** | `tu_khoa` *(bắt buộc)* | Tìm kiếm món đồ uống siêu tốc theo tên hoặc vị (matcha, muối, dừa, bơ...). |
| **`/gio-hang`** | *Không* | Xem giỏ hàng cá nhân, tổng thanh toán tạm tính và nút **[💳 Xác Nhận Đặt Đơn]** hoặc **[🗑️ Xóa Sạch Giỏ Hàng]**. |
| **`/so-thich`** | `muc_ngot`<br>`muc_da`<br>`khau_vi`<br>`di_ung` | Cài đặt khẩu vị mặc định của bạn. Khi bấm Đặt món, bot sẽ tự động điền sẵn các mức này! |
| **Chat Tự Nhiên** | `@Bot <câu hỏi>` | Có thể nhắc tên Bot trực tiếp trong kênh chat để hỏi nhanh đồ uống mà không cần gõ lệnh. |

---

## 4. Hướng Dẫn Thiết Lập & Khởi Chạy

### Bước 1: Tạo Bot trên Discord Developer Portal
1. Truy cập [Discord Developer Portal](https://discord.com/developers/applications).
2. Bấm **New Application** $\rightarrow$ Đặt tên cho ứng dụng (ví dụ: `Quán Nước AI`).
3. Vào mục **Bot** $\rightarrow$ Bấm **Reset Token** để lấy Bot Token.
4. Kéo xuống mục **Privileged Gateway Intents** $\rightarrow$ Bật công tắc **Message Content Intent** (để bot đọc được tin nhắn khi tag bot).
5. Vào mục **OAuth2** $\rightarrow$ **URL Generator**:
   - Chọn scope: `bot` và `applications.commands`.
   - Chọn Bot Permissions: `Send Messages`, `Embed Links`, `Attach Files`, `Read Message History`, `Use Slash Commands`.
   - Copy đường link được tạo và dán vào trình duyệt để mời bot vào Server Discord của bạn.

### Bước 2: Cấu hình Token vào file `.env`
Mở file `.env` tại thư mục dự án và điền:
```env
DISCORD_BOT_TOKEN=dien_token_cua_ban_tai_day
DISCORD_GUILD_ID=dien_server_id_cua_ban_neu_muon_sync_slash_tuc_thi
```
*(Nếu điền `DISCORD_GUILD_ID`, các Slash Commands sẽ có hiệu lực ngay lập tức trong Server đó thay vì phải chờ Discord đồng bộ toàn cầu).*

### Bước 3: Khởi chạy Bot
Chạy lệnh sau tại terminal:
```powershell
python "Khởi Chạy Bot.py"
```

Khi terminal hiện:
```text
[INFO] Đã kích hoạt tăng tốc GPU: NVIDIA GeForce RTX 4080 Laptop GPU
[INFO] Đã nạp 20 món vào bộ nhớ đệm Bộ Máy Gợi Ý.
[INFO] Đã đăng nhập thành công bot: Quán Nước AI
[INFO] Đã đồng bộ 5 Slash Commands tức thì vào Guild ...
```
Bot đã sẵn sàng phục vụ 24/7!
