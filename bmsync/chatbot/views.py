from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import json
from django.contrib.auth.decorators import login_required
from dashboard.models import Device, MaintenanceRequest, MaintenanceTask
from users.models import UserProfile

@login_required
def chatbot_view(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        user_message = data.get('message', '')
        user_role = data.get('role', '')
        
        # Xử lý theo vai trò người dùng
        if user_role == 'tenant':
            return handle_tenant_query(request, user_message)
        elif user_role == 'manager':
            return handle_manager_query(request, user_message)
        else:
            # Xử lý mặc định
            return JsonResponse({'response': "Tôi chưa hiểu câu hỏi. Vui lòng hỏi lại hoặc cụ thể hơn."})
    
    return render(request, 'chatbot/chatbot.html')

@csrf_exempt
def send_message(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        user_message = data.get('message', '')
        user_role = data.get('role', '')
        
        # Xử lý theo vai trò người dùng
        if user_role == 'tenant':
            return handle_tenant_query(request, user_message)
        elif user_role == 'manager':
            return handle_manager_query(request, user_message)
        else:
            # Xử lý mặc định
            return JsonResponse({'response': "Tôi chưa hiểu câu hỏi. Vui lòng hỏi lại hoặc cụ thể hơn."})
    
    return JsonResponse({'response': "Phương thức không được hỗ trợ"}, status=405)

def handle_tenant_query(request, user_message):
    user_profile = request.user.profile
    
    # Chuyển đổi câu hỏi sang chữ thường để dễ xử lý
    query = user_message.lower()
    
    # Xem danh sách thiết bị
    if any(keyword in query for keyword in ['danh sách thiết bị', 'thiết bị của tôi', 'liệt kê thiết bị', 'xem thiết bị']):
        devices = Device.objects.filter(tenant=user_profile)
        if not devices:
            return JsonResponse({'response': "Bạn chưa có thiết bị nào được đăng ký."})
        
        # Tạo bảng Markdown
        markdown_table = "## Danh sách thiết bị của bạn\n\n"
        markdown_table += "| STT | Tên thiết bị | Loại | Vị trí | Trạng thái |\n"
        markdown_table += "|-----|-------------|------|--------|------------|\n"
        
        for i, device in enumerate(devices, 1):
            device_type_display = device.get_device_type_display()
            status_display = device.get_status_display()
            markdown_table += f"| {i} | {device.name} | {device_type_display} | {device.location} | {status_display} |\n"
        
        return JsonResponse({'response': markdown_table})
    
    # Xem yêu cầu bảo trì
    elif any(keyword in query for keyword in ['yêu cầu bảo trì', 'danh sách bảo trì', 'xem bảo trì', 'liệt kê bảo trì']):
        maintenance_requests = MaintenanceRequest.objects.filter(requester=user_profile)
        if not maintenance_requests:
            return JsonResponse({'response': "Bạn chưa có yêu cầu bảo trì nào."})
        
        # Tạo bảng Markdown
        markdown_table = "## Danh sách yêu cầu bảo trì của bạn\n\n"
        markdown_table += "| STT | Tiêu đề | Thiết bị | Trạng thái | Ưu tiên | Ngày tạo |\n"
        markdown_table += "|-----|--------|----------|------------|---------|----------|\n"
        
        for i, req in enumerate(maintenance_requests, 1):
            device_name = req.device.name if req.device else "N/A"
            status_display = req.get_status_display()
            priority_display = req.get_priority_display()
            created_at = req.created_at.strftime("%d/%m/%Y")
            markdown_table += f"| {i} | {req.title} | {device_name} | {status_display} | {priority_display} | {created_at} |\n"
        
        return JsonResponse({'response': markdown_table})
    
    # Xem lịch sử bảo trì
    elif any(keyword in query for keyword in ['lịch sử bảo trì', 'đã hoàn thành', 'công việc hoàn thành']):
        completed_tasks = MaintenanceTask.objects.filter(
            maintenance_request__requester=user_profile, 
            status='completed'
        )
        
        if not completed_tasks:
            return JsonResponse({'response': "Bạn chưa có công việc bảo trì nào đã hoàn thành."})
        
        # Tạo bảng Markdown
        markdown_table = "## Lịch sử công việc bảo trì đã hoàn thành\n\n"
        markdown_table += "| STT | Công việc | Thiết bị | Ngày hoàn thành | Nhân viên | Đánh giá |\n"
        markdown_table += "|-----|----------|----------|-----------------|-----------|----------|\n"
        
        for i, task in enumerate(completed_tasks, 1):
            device_name = task.maintenance_request.device.name if task.maintenance_request.device else "N/A"
            due_date = task.due_date.strftime("%d/%m/%Y")
            assigned_to = task.assigned_to.user.get_full_name() if task.assigned_to else "N/A"
            rating = f"{task.rating}/5" if task.rating else "Chưa đánh giá"
            markdown_table += f"| {i} | {task.title} | {device_name} | {due_date} | {assigned_to} | {rating} |\n"
        
        return JsonResponse({'response': markdown_table})
    
    # Hướng dẫn tạo yêu cầu bảo trì
    elif any(keyword in query for keyword in ['tạo yêu cầu', 'tạo bảo trì', 'yêu cầu mới', 'hướng dẫn']):
        response = """## Hướng dẫn tạo yêu cầu bảo trì mới

1. Đi đến trang "Thiết bị của tôi" từ menu bên trái
2. Tìm thiết bị cần bảo trì và nhấn vào nút "Chi tiết"
3. Trong trang chi tiết thiết bị, nhấn vào nút "Yêu cầu bảo trì"
4. Điền các thông tin cần thiết:
   - Tiêu đề: Mô tả ngắn gọn vấn đề
   - Mô tả: Chi tiết về vấn đề bạn gặp phải
   - Mức độ ưu tiên: Chọn mức độ khẩn cấp
5. Nhấn "Gửi yêu cầu" để hoàn tất

Bạn cũng có thể tạo yêu cầu bảo trì từ trang Dashboard bằng cách nhấn vào nút "Yêu cầu thêm thiết bị" ở trên đầu trang."""
        
        return JsonResponse({'response': response})
    
    # Thống kê tổng quan
    elif any(keyword in query for keyword in ['thống kê', 'tổng quan', 'thông tin tổng hợp', 'dashboard']):
        devices = Device.objects.filter(tenant=user_profile)
        maintenance_requests = MaintenanceRequest.objects.filter(requester=user_profile)
        completed_requests = MaintenanceTask.objects.filter(
            maintenance_request__requester=user_profile, 
            status='completed'
        ).count()
        
        response = f"""## Thống kê tổng quan

- **Tổng số thiết bị**: {devices.count()}
- **Tổng số yêu cầu bảo trì**: {maintenance_requests.count()}
- **Yêu cầu đã hoàn thành**: {completed_requests}

Bạn có thể xem chi tiết hơn về từng mục bằng cách hỏi tôi về "danh sách thiết bị", "danh sách yêu cầu bảo trì" hoặc "lịch sử bảo trì"."""
        
        return JsonResponse({'response': response})
    
    # Trợ giúp
    elif any(keyword in query for keyword in ['trợ giúp', 'help', 'giúp đỡ', 'hướng dẫn sử dụng']):
        response = """## Tôi có thể giúp gì cho bạn?

Tôi có thể hỗ trợ bạn với các thông tin sau:

- **Xem danh sách thiết bị** của bạn
- **Xem danh sách yêu cầu bảo trì** của bạn
- **Xem lịch sử bảo trì** đã hoàn thành
- **Hướng dẫn tạo yêu cầu bảo trì** mới
- **Xem thống kê tổng quan** về thiết bị và yêu cầu bảo trì

Hãy hỏi tôi về bất kỳ chủ đề nào trên đây!"""
        
        return JsonResponse({'response': response})
    
    # Mặc định
    else:
        response = """Tôi chưa hiểu rõ yêu cầu của bạn. Tôi có thể giúp bạn với:

- Xem danh sách thiết bị
- Xem danh sách yêu cầu bảo trì
- Xem lịch sử bảo trì
- Hướng dẫn tạo yêu cầu bảo trì
- Xem thống kê tổng quan

Vui lòng hỏi lại với một trong những chủ đề trên."""
        
        return JsonResponse({'response': response})

def handle_manager_query(request, user_message):
    # Xử lý truy vấn từ Manager (có thể mở rộng sau)
    return JsonResponse({'response': "Tôi đang xử lý yêu cầu của Manager. Tính năng này đang được phát triển."})
