# 🌟 GeminiBridge - Cổng Kết Nối Gemini Dùng Chung Cho Các Công Cụ AI

> **Dành cho người không biết lập trình:** Bạn không cần phải viết bất kỳ dòng mã nào! Dự án đã được thiết lập sẵn toàn bộ công cụ tự động. Bạn chỉ cần nhấp đúp vào `start.bat` là có thể dùng ngay.

---

## 🎯 Mục Tiêu Của GeminiBridge

`GeminiBridge` đóng vai trò như một **trạm trung chuyển AI cục bộ (Local AI Proxy)** ngay trên máy tính Windows của bạn:
- **Biến Cookie tài khoản Gemini web cá nhân thành cổng API dùng chung** theo chuẩn OpenAI (`/v1/chat/completions`).
- Cho phép hàng loạt phần mềm AI khác nhau (như **Chatbox, NextChat, Cherry Studio, Continue, Cursor, LibreChat, Dify, Obsidian...**) cắm vào và trò chuyện trực tiếp với tài khoản Gemini cá nhân của bạn.
- Hỗ trợ cả 2 chế độ:
  1. **WebAPI (Cookie):** Sử dụng tài khoản cá nhân thông qua cookie `__Secure-1PSID`.
  2. **Official API (Khóa API chính thức):** Sử dụng khóa API từ Google AI Studio.

---

## 🚀 Hướng Dẫn Sử Dụng Nhanh (Chỉ Cần 1 Cú Nhấp Chuột)

Cookie tài khoản cá nhân của bạn đã được nạp an toàn vào file cấu hình [`.env`](file:///d:/API%20Ca%20Nhan/.env).

### Khởi động máy chủ:
1. Mở thư mục `d:\API Ca Nhan`.
2. **Nhấp đúp chuột vào file:** [`start.bat`](file:///d:/API%20Ca%20Nhan/start.bat).
3. Máy chủ sẽ khởi động và **tự động mở trình duyệt web** đến trang điều khiển:
   👉 **http://127.0.0.1:8200**
4. Bạn sẽ thấy trạng thái:
   - **Trạng thái Server:** `Đang hoạt động (Running)`
   - **Trạng thái Xác thực:** `Cookie WebAPI (Đã nạp)`
   - **Mô hình:** `gemini-2.0-flash`
   - **Kiểu kết nối:** `webapi`

> 💡 **Mẹo:** Khi không sử dụng nữa, bạn chỉ cần đóng cửa sổ đen (CMD) lại. Khi nào muốn dùng lại, chỉ cần nhấp đúp vào `start.bat`.

---

## 🔌 Cách Kết Nối Vào Các Phần Mềm AI Của Bạn

Bây giờ mọi phần mềm AI trên máy tính của bạn đều có thể trò chuyện với tài khoản Gemini cá nhân thông qua cổng chuẩn OpenAI:

| Mục Cấu Hình Trong App AI | Giá Trị Cần Điền |
| :--- | :--- |
| **Loại API (API Type / Provider)** | Chọn `OpenAI` hoặc `OpenAI Compatible` |
| **Địa Chỉ API (Base URL / API Host)** | `http://127.0.0.1:8200/v1` |
| **API Key** | Điền bất kỳ ký tự nào (ví dụ: `sk-gemini`) hoặc để trống |
| **Tên Mô Hình Chat (Model)** | `gemini-2.0-flash` (hoặc `gemini-1.5-flash`, `gemini-1.5-pro`) |
| **Tên Mô Hình Video (Model)** | `google-flow` (Cinematic AI Veo) hoặc `google-vids` (Workspace Omni) |

### Ví dụ cấu hình cụ thể trên các ứng dụng:
- **Chatbox:** Cài đặt -> Chọn Nhà cung cấp: `OpenAI API` -> API Host: `http://127.0.0.1:8200` -> API Path: `/v1` -> Model: `gemini-2.0-flash`.
- **NextChat (ChatGPT-Next-Web):** Cài đặt -> Custom Endpoint: Bật ON -> URL: `http://127.0.0.1:8200` -> Model: `gemini-2.0-flash`.
- **Cherry Studio:** Cài đặt -> Quản lý nhà cung cấp -> Thêm OpenAI tương thích -> Base URL: `http://127.0.0.1:8200/v1`.
- **Continue / Cursor (VS Code):** Trong file cấu hình `config.json`, đặt `apiBase`: `http://127.0.0.1:8200/v1`.

---

## 🎬 Tạo Video AI Tự Động (Google Flow & Google Vids)

Hệ thống hỗ trợ tạo video trực tiếp bằng tài khoản Google cá nhân của bạn trên 2 nền tảng:
1. **Google Flow (flow.google.com):** Tạo video cinematic bằng mô hình Veo / Gemini Omni Flash thế hệ mới.
2. **Google Vids (vids.new):** Tạo video thuyết trình, kịch bản phân cảnh của Google Workspace.

### 2 Cách Sử Dụng:
- **Cách 1: Dùng trực tiếp trên trang chủ (Không cần code):**
  1. Mở `http://127.0.0.1:8200` trên trình duyệt.
  2. Chọn `Google Flow` hoặc `Google Vids`.
  3. Nhập mô tả kịch bản video và bấm **"Tạo Video Ngay"**.
  4. Xem video phát trực tiếp trên trình phát và tải file MP4 về máy!
- **Cách 2: Gọi qua API chuẩn OpenAI:**
  - Endpoint: `POST http://127.0.0.1:8200/v1/videos/generations`
  - Body:
    ```json
    {
      "prompt": "Cinematic drone shot of turquoise ocean waves at sunset",
      "model": "google-flow"
    }
    ```

---

## 🧪 Cách Kiểm Tra API Hoạt Động (Không Cần Code)

Bạn có thể kiểm tra trực tiếp khả năng trả lời của AI trên trình duyệt:

1. Mở trình duyệt và truy cập: **http://127.0.0.1:8200/docs** (Giao diện Swagger UI).
2. Tìm dòng **`POST /v1/chat/completions`**, **`POST /v1/images/generations`** hoặc **`POST /v1/videos/generations`** ➔ Nhấp vào.
3. Bấm nút **Try it out** (góc phải).
4. Nhập nội dung câu hỏi muốn hỏi AI ➔ Bấm nút **Execute** màu xanh.
5. Xem kết quả trả về trực tiếp!

Ngoài ra, bạn có thể nhấp đúp vào file [`test.bat`](file:///d:/API%20Ca%20Nhan/test.bat) để tự động kiểm tra 24 bài test hệ thống hoàn chỉnh.

---

## 🔒 Quản Lý Cookie & An Toàn Bảo Mật

1. **Bảo mật tuyệt đối:**
   - Cookie tài khoản được lưu trữ an toàn trong file cục bộ [`.env`](file:///d:/API%20Ca%20Nhan/.env) trên máy tính của bạn.
   - File [`.gitignore`](file:///d:/API%20Ca%20Nhan/.gitignore) ngăn chặn hoàn toàn việc vô tình đẩy file `.env` lên GitHub hay internet.
   - Không có cơ chế tự động quét trộm cookie từ trình duyệt; toàn bộ kết nối chỉ diễn ra cục bộ trong máy tính của bạn (`127.0.0.1`).
2. **Khi Cookie Hết Hạn:**
   - Cookie tài khoản Google Web có thể hết hạn sau một khoảng thời gian.
   - Nếu phần mềm AI báo lỗi không nhận được phản hồi:
     - Bạn vào trang [gemini.google.com](https://gemini.google.com) trên trình duyệt, nhấn **F12** -> chọn tab **Application** (hoặc Lưu trữ) -> mục **Cookies**.
     - Tìm giá trị của cookie `__Secure-1PSID`.
     - Mở file `.env` bằng Notepad và dán giá trị mới vào dòng `GEMINI_SECURE_1PSID=...`.
     - Lưu lại file `.env` là xong!

---

## 📁 Cấu Trúc Thư Mục Dự Án

```text
d:\API Ca Nhan\
├── app/
│   ├── clients/                  # Các bộ điều hợp kết nối Gemini & Video
│   │   ├── base.py               # Lớp nền trừu tượng BaseGeminiClient
│   │   ├── official_client.py    # Kết nối Google Gemini API chính thức
│   │   ├── browser_adapter.py    # Điều khiển Edge/Chrome (Gemini & Imagen 3)
│   │   ├── video_generator.py    # Bộ tự động hóa tạo video (Google Flow & Vids)
│   │   ├── webapi_adapter.py     # Bộ điều hợp kết nối Gemini Web qua Cookie
│   │   └── factory.py            # Quản lý chuyển đổi client linh hoạt
│   ├── models/                   # Định dạng dữ liệu chuẩn REST, OpenAI và Video
│   ├── routes/                   # Các endpoint API (/health, /api, /v1, /api/video)
│   ├── config.py                 # Nạp cấu hình từ .env
│   └── main.py                   # FastAPI Server & Giao diện điều khiển
├── outputs/                      # Thư mục lưu trữ media tự động
│   ├── generated_images/         # Ảnh Imagen 3
│   └── generated_videos/         # Video Google Flow & Google Vids (.mp4)
├── docs/
│   └── gemini_webapi_research.md # Báo cáo nghiên cứu kỹ thuật
├── tests/                        # Bộ 24 bài kiểm tra tự động hệ thống
├── .env                          # File chứa cấu hình & cookie của bạn (Bảo mật)
├── .env.example                  # File cấu hình mẫu
├── .gitignore                    # Chặn lộ cookie/key lên GitHub
├── requirements.txt              # Danh sách thư viện cần thiết
├── setup.bat                     # Nhấp đúp: Tự động cài đặt ban đầu
├── start.bat                     # Nhấp đúp: Khởi động máy chủ & tự mở trình duyệt
├── test.bat                      # Nhấp đúp: Tự động chạy kiểm tra hệ thống (24 tests)
└── README.md                     # Hướng dẫn chi tiết bằng tiếng Việt
```

