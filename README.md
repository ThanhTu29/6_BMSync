# Ứng dụng Quản lý Trang Thiết bị trong một Tòa Nhà (BMSync)

## Tên ứng dụng: BMSync
BMSync là một ứng dụng web chuyên quản lý trang thiết bị cho tòa nhà cho thuê văn phòng và phòng học. Ứng dụng hỗ trợ theo dõi, vận hành và bảo trì thiết bị một cách minh bạch, hiệu quả, đáp ứng nhu cầu của từng nhóm người dùng.

## Đối tượng người dùng
- **Admin**: Toàn quyền trên hệ thống—quản lý tài khoản, phân quyền, cấu hình, báo cáo tổng thể.
- **Manager**: Quản lý thực địa—giám sát hoạt động, phân công công việc, theo dõi tiến độ.
- **Nhân viên bảo trì**: Thực hiện công tác bảo trì/sửa chữa, cập nhật trạng thái và báo cáo kết quả.
- **Người thuê (Tenant)**: Xem trạng thái thiết bị, gửi yêu cầu sửa chữa, theo dõi tiến trình và đánh giá sau bảo trì.

## Các chức năng chính

### 1. Quản lý đăng nhập & phân quyền
- Đăng ký, đăng nhập, đăng xuất.
- Phân quyền theo vai trò (Admin, Manager, Maint, Tenant).

### 2. Quản lý trang thiết bị
- CRUD thiết bị: mã, tên, loại, vị trí (tòa nhà, tầng, phòng).
- Phân loại theo nhóm (office, classroom, thiết bị chung).
- Tìm kiếm, lọc theo tình trạng (hoạt động, hỏng, đang bảo trì).

### 3. Quản lý vị trí & không gian
- Quản lý tòa nhà, khu vực, tầng, phòng.
- Liên kết thiết bị với phòng/zone cụ thể.

### 4. Quy trình bảo trì & sửa chữa
- Khởi tạo yêu cầu bảo trì từ Tenant hoặc Manager.
- Manager phân công nhiệm vụ cho nhân viên bảo trì.
- Nhân viên nhận thông báo, thực hiện và cập nhật kết quả.
- Tenant theo dõi tiến độ và đánh giá sau khi hoàn thành.

### 5. Thông báo & cảnh báo
- Gửi email/SMS khi có yêu cầu mới, đến hạn bảo trì hoặc sự cố.
- Dashboard hiển thị cảnh báo quan trọng.

### 6. Báo cáo & Thống kê
- Báo cáo số lượng thiết bị theo loại, tình trạng, vị trí.
- Thống kê yêu cầu bảo trì theo thời gian (ngày, tuần, tháng).
- Dashboard trực quan: số thiết bị cần bảo trì, tỷ lệ hoàn thành, hiệu suất nhân viên.

### 7. Quản lý người dùng
- Admin: tạo, sửa, xóa tài khoản, phân quyền.
- Manager: xem danh sách nhân viên & Tenant, khóa/mở tài khoản khi cần.

### 8. Chatbot hỗ trợ
- Chatbot AI tích hợp trên giao diện web: trả lời tự động các câu hỏi thường gặp về sử dụng và vận hành thiết bị.
- Hướng dẫn quy trình bảo trì, báo cáo sự cố, tạo yêu cầu tự động qua chat.
- Hỗ trợ 24/7, cải thiện trải nghiệm người dùng và giảm tải công việc cho bộ phận hỗ trợ.

