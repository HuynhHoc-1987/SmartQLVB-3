# Tạo file thực thi SmartQLVB bằng GitHub Actions

1. Đăng nhập GitHub, tạo **repository riêng tư (Private)** tên `SmartQLVB`.
2. Trên máy tính, giải nén `SmartQLVB_GitHub_Source.zip`, mở thư mục dự án. Đưa **nội dung bên trong** lên repository (có `server.py` và `.github/workflows/windows-exe.yml` ở thư mục gốc). Có thể dùng **Add file → Upload files**, nhưng phải bảo đảm thư mục ẩn `.github` được tải lên đúng cấu trúc; sử dụng GitHub Desktop sẽ thuận tiện hơn.
3. Vào **Actions → Dong goi SmartQLVB Windows → Run workflow → Run workflow**.
4. Chờ dấu tích xanh, mở lần chạy → **Artifacts** → tải `SmartQLVB_Windows_x64`.
5. Giải nén artifact, sau đó giải nén `SmartQLVB_Windows_x64.zip` vào `D:\SmartQLVB`.
6. Chạy `SmartQLVB.exe`. Cài tiện ích Chrome theo `README_CAI_DAT.txt`.

**Chú ý:** Chạy Actions sẽ gửi mã nguồn đến máy chủ GitHub, không gửi dữ liệu văn bản vì gói nguồn không chứa `DU_LIEU`. Không đưa tài liệu mật, mã ghép nối, token, PDF công việc vào repository. GitHub-hosted Windows build cần mạng để cài thư viện. EXE chưa ký số. Bản build cần kiểm thử trên Windows thật.

**Đóng gói tại Windows không cần GitHub:** cài Python 3.11, mở PowerShell tại thư mục nguồn và chạy `./build_windows.ps1` (nếu chính sách PowerShell cho phép). Kết quả ở `dist/SmartQLVB_Windows_x64.zip`.
