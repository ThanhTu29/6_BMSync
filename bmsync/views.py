from django.shortcuts import render, redirect
from django.db import models # Required for Q objects if not already imported
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import Group
from django.contrib.auth.forms import UserCreationForm # Sẽ cần UserChangeForm và tùy chỉnh form sau
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.contrib import messages
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger # Đã có ở trên, đảm bảo import
from django.contrib.auth import update_session_auth_hash, logout
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.sessions.models import Session
from django.utils import timezone
from .models import User, Device, MaintenanceRequest, Notification # Ensure Notification is imported
from django.contrib.auth import get_user_model # Thêm import này
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string # For HTML emails later if needed
from django.contrib.auth.decorators import login_required
import logging
from dashboard.models import MaintenanceTask
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json
import google.generativeai as genai
import requests

logger = logging.getLogger(__name__)


@login_required
def settings_view(request):
    return render(request, 'bmsync/settings.html')

def base_view(request):
    # Chuyển hướng đến view home để xử lý đúng vai trò người dùng
    return redirect('home')  # Đảm bảo 'home' là tên URL pattern cho hàm home

def home(request):
    if not request.user.is_authenticated:
        return render(request, 'bmsync/home.html')
    
    # Xác định vai trò của người dùng
    user_role = None
    if hasattr(request.user, 'profile'):
        user_role = request.user.profile.role_type
        # Debug để kiểm tra vai trò
        print(f"[DEBUG] User role: {user_role}")
    else:
        print("[DEBUG] User doesn't have profile")
    
    # Truyền thông tin vai trò và dữ liệu liên quan đến template
    context = {
        'user_role': user_role,
    }
    
    # Thêm dữ liệu tùy theo vai trò
    if user_role == 'manager':
        from .models import Device, MaintenanceRequest, Notification

        # Tổng thiết bị (không lọc theo manager vì không có trường liên kết)
        total_devices = Device.objects.count()

        # Yêu cầu bảo trì mà manager này là người xử lý
        maintenance_requests = MaintenanceRequest.objects.filter(assigned_to=request.user)
        pending_requests = maintenance_requests.filter(status__in=['new', 'pending', 'in_progress']).count()
        critical_alerts = maintenance_requests.filter(priority=1, status__in=['new', 'pending']).count()
        completed_maintenance = maintenance_requests.filter(status='completed').count()

        unread_notifications = Notification.objects.filter(
            recipient=request.user, 
            is_read=False
        ).count()

        # Tính tỷ lệ hoạt động (tạm thời lấy tổng thiết bị đang hoạt động)
        operational_devices = Device.objects.filter(status='active').count()
        total_device_count = total_devices or 1
        operational_rate = int((operational_devices / total_device_count) * 100)

        context.update({
            'total_devices': total_devices,
            'maintenance_requests': pending_requests + completed_maintenance,
            'pending_requests': pending_requests,
            'critical_alerts': critical_alerts,
            'completed_maintenance': completed_maintenance,
            'operational_rate': operational_rate,
            'new_notifications': unread_notifications,
        })
    elif user_role == 'maintenance':
        user_profile = request.user.profile
        maintenance_tasks = MaintenanceTask.objects.filter(assigned_to=user_profile)
        new_tasks = maintenance_tasks.filter(status='pending').count()
        processing_tasks = maintenance_tasks.filter(status='in_progress').count()
        completed_tasks = maintenance_tasks.filter(status='completed').count()
        context.update({
            'assigned_tasks': maintenance_tasks.count(),
            'new_tasks': new_tasks,
            'processing_tasks': processing_tasks,
            'completed_tasks': completed_tasks,
        })
    elif user_role == 'tenant':
        from dashboard.models import MaintenanceRequest, Device
        user_profile = request.user.profile
        my_devices = Device.objects.filter(tenant=user_profile)
        my_requests = MaintenanceRequest.objects.filter(requester=user_profile)
        pending_requests = my_requests.filter(status='pending').count()
        completed_requests = my_requests.filter(status='completed').count()
        context.update({
            'my_devices': my_devices.count(),
            'my_requests': my_requests.count(),
            'pending_requests': pending_requests,
            'completed_requests': completed_requests,
            'maintenance_history': completed_requests,
        })
    
    return render(request, 'bmsync/home.html', context)

def developing_view(request):
    return render(request, 'developing.html')

def feature_developing(request):
    return render(request, 'feature_developing.html', {'message': 'Tính năng này đang được phát triển bởi nhóm 6'})

def about_view(request):
    return render(request, 'bmsync/about.html')

def services_view(request):
    return render(request, 'bmsync/services.html')

def contact_view(request):
    return render(request, 'bmsync/contact.html')

@login_required
def mark_notification_as_read(request, notification_id):
    notification = get_object_or_404(Notification, pk=notification_id, recipient=request.user)
    if not notification.is_read:
        notification.is_read = True
        notification.save()
        messages.success(request, 'Thông báo đã được đánh dấu là đã đọc.')
    next_url = request.GET.get('next', 'home') 
    return redirect(next_url)

@login_required
def user_notifications_view(request):
    notifications = Notification.objects.filter(recipient=request.user).order_by('-timestamp')
    paginator = Paginator(notifications, 15)
    page_number = request.GET.get('page')
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    base_template = 'admin/admin_base.html' if request.user.is_staff else 'base.html'
    # Đếm số thông báo chưa đọc cho admin_base template (nếu cần thiết ở đây, thường là trong context processor)
    unread_notifications_count = 0
    if request.user.is_staff:
        unread_notifications_count = Notification.objects.filter(recipient=request.user, is_read=False).count()

    return render(request, 'bmsync/user_notifications.html', {
        'page_obj': page_obj, 
        'base_template_to_extend': base_template, # Đổi tên biến để rõ ràng hơn trong template
        'unread_notifications_count': unread_notifications_count # Truyền cho admin_base nếu nó dùng
        })

@login_required
def change_password(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Mật khẩu của bạn đã được thay đổi thành công!')
            return redirect('home')
        else:
            messages.error(request, 'Vui lòng sửa các lỗi bên dưới.')
    else:
        form = PasswordChangeForm(request.user)
    return render(request, 'registration/change_password.html', {
        'form': form
    })

from django.utils import timezone
from datetime import timedelta
from django.db.models import Count, Sum, Avg, Min, Max # Thêm các hàm tổng hợp cần thiết

@staff_member_required
def admin_dashboard(request):
    # Thông tin nhanh
    total_devices = Device.objects.count()
    broken_devices = Device.objects.filter(status='Hỏng').count()
    maintenance_devices = Device.objects.filter(status='Đang bảo trì').count()
    
    # Sắp tới hạn bảo trì: các yêu cầu bảo trì có ngày hẹn trong 7 ngày tới và chưa hoàn thành
    # Giả định MaintenanceRequest có trường 'due_date' hoặc 'scheduled_maintenance_date'
    # và trường 'status' để biết đã hoàn thành hay chưa.
    # Ví dụ: status 'Chờ xử lý', 'Đang tiến hành' là chưa hoàn thành.
    upcoming_maintenance_deadline = timezone.now().date() + timedelta(days=7)
    upcoming_maintenances_count = MaintenanceRequest.objects.filter(
        # scheduled_maintenance_date__date__gte=timezone.now().date(), # Lấy từ ngày hiện tại
        # scheduled_maintenance_date__date__lte=upcoming_maintenance_deadline,
        status__in=['Chờ xử lý', 'Đang tiến hành'] # Các trạng thái chưa hoàn thành
    ).count()
    # Nếu không có trường ngày cụ thể, có thể đếm các yêu cầu 'Chờ xử lý' làm ví dụ
    # upcoming_maintenances_count = MaintenanceRequest.objects.filter(status='Chờ xử lý').count()

    # Dữ liệu cho biểu đồ "Yêu cầu bảo trì (Theo thời gian)"
    # Đếm số lượng yêu cầu bảo trì theo tháng trong 6 tháng gần nhất (bao gồm tháng hiện tại)
    maintenance_requests_by_month_labels = []
    maintenance_requests_by_month_data = []
    today = timezone.now()
    for i in range(5, -1, -1): # 6 tháng, từ tháng (hiện tại - 5) đến tháng hiện tại
        # Tính toán tháng và năm cho từng điểm dữ liệu
        target_month = today.month - i
        target_year = today.year
        if target_month <= 0:
            target_month += 12
            target_year -= 1
        
        count = MaintenanceRequest.objects.filter(report_date__year=target_year, report_date__month=target_month).count()
        maintenance_requests_by_month_labels.append(f'Tháng {target_month}/{target_year % 100}')
        maintenance_requests_by_month_data.append(count)

    # Dữ liệu cho biểu đồ "Phân bổ thiết bị (Theo tình trạng)"
    device_status_distribution = Device.objects.values('status').annotate(count=Count('status')).order_by('status')
    device_status_labels = [item['status'] for item in device_status_distribution]
    device_status_data = [item['count'] for item in device_status_distribution]

    # Cảnh báo nổi bật
    # Yêu cầu bảo trì có trạng thái 'Chờ xử lý' hoặc 'Cần chú ý' (nếu có)
    # Sắp xếp theo ngày tạo cũ nhất trước
    pending_maintenance_requests = MaintenanceRequest.objects.filter(
        status__in=['Chờ xử lý'] # Thêm các trạng thái khác nếu cần
    ).order_by('report_date')[:5] # Lấy 5 cảnh báo mới nhất (hoặc cũ nhất tùy logic)
    
    # Thiết bị hỏng chưa được xử lý (chưa có yêu cầu bảo trì hoặc yêu cầu chưa được giải quyết)
    critical_devices_alert = Device.objects.filter(status='Hỏng').order_by('-updated_at')[:5]

    # Lấy các thông báo chưa đọc cho admin (nếu có)
    unread_notifications_count = Notification.objects.filter(recipient=request.user, is_read=False).count()

    # Lấy thời gian đăng nhập cuối cùng từ session (nếu được lưu bởi middleware hoặc view login)
    last_login_time = request.session.get('last_login_time', request.user.last_login.strftime("%H:%M %d/%m/%Y") if request.user.last_login else 'N/A')

    context = {
        'total_devices': total_devices,
        'broken_devices': broken_devices,
        'maintenance_devices': maintenance_devices,
        'upcoming_maintenances_count': upcoming_maintenances_count,
        'maintenance_requests_by_month_labels': maintenance_requests_by_month_labels,
        'maintenance_requests_by_month_data': maintenance_requests_by_month_data,
        'device_status_labels': device_status_labels,
        'device_status_data': device_status_data,
        'pending_maintenance_requests': pending_maintenance_requests,
        'critical_devices_alert': critical_devices_alert,
        'unread_notifications_count': unread_notifications_count,
        'last_login_time': last_login_time
    }
    return render(request, 'admin/admin_dashboard.html', context)

from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from .models import Device

from django.contrib import messages

@staff_member_required
def admin_quan_ly_thiet_bi(request):
    if request.method == 'POST' and request.POST.get('form_action') == 'add_device':
        device_id = request.POST.get('device_id')
        name = request.POST.get('name')
        device_type = request.POST.get('device_type')
        status = request.POST.get('status')
        location = request.POST.get('location')
        purchase_date = request.POST.get('purchase_date')
        warranty_expiry_date = request.POST.get('warranty_expiry_date')
        description = request.POST.get('description')

        # Basic validation (can be improved with Django Forms)
        if not device_id or not name:
            messages.error(request, 'ID thiết bị và Tên thiết bị là bắt buộc.')
        elif Device.objects.filter(device_id=device_id).exists():
            messages.error(request, f'ID thiết bị "{device_id}" đã tồn tại. Vui lòng sử dụng ID khác.')
        else:
            try:
                Device.objects.create(
                    device_id=device_id,
                    name=name,
                    device_type=device_type,
                    status=status,
                    location=location,
                    purchase_date=purchase_date if purchase_date else None,
                    warranty_expiry_date=warranty_expiry_date if warranty_expiry_date else None,
                    description=description
                )
                messages.success(request, f'Thiết bị "{name}" đã được thêm thành công.')
                return redirect('admin_quan_ly_thiet_bi')
            except Exception as e:
                messages.error(request, f'Có lỗi xảy ra khi thêm thiết bị: {e}')

    # Sắp xếp theo -id để thiết bị mới nhất lên đầu
    devices_list = Device.objects.all().order_by('-id')
    query = request.GET.get('q')
    status_filter = request.GET.get('status')
    type_filter = request.GET.get('type')

    if query:
        devices_list = devices_list.filter(
            models.Q(name__icontains=query) |
            models.Q(device_id__icontains=query) |
            models.Q(location__icontains=query)
        ).distinct()

    if status_filter and status_filter != 'all':
        devices_list = devices_list.filter(status=status_filter)
    
    if type_filter and type_filter != 'all':
        devices_list = devices_list.filter(device_type=type_filter)

    # Lấy giá trị items_per_page từ cài đặt người dùng hoặc mặc định
    # Tạm thời để 10, sau này sẽ lấy từ model UserProfile hoặc Settings
    items_per_page = request.GET.get('items_per_page', 10) 
    paginator = Paginator(devices_list, items_per_page)
    page = request.GET.get('page')

    try:
        devices = paginator.page(page)
    except PageNotAnInteger:
        devices = paginator.page(1)
    except EmptyPage:
        devices = paginator.page(paginator.num_pages)

    context = {
        'devices': devices,
        'status_choices': Device.STATUS_CHOICES,
        'type_choices': Device.TYPE_CHOICES,
        'current_query': query or '',
        'current_status': status_filter or 'all',
        'current_type': type_filter or 'all',
        'items_per_page': int(items_per_page)
    }
    return render(request, 'admin/admin_quan_ly_thiet_bi.html', context)

@staff_member_required
def admin_them_thiet_bi(request):
    if request.method == 'POST':
        device_id_req = request.POST.get('device_id')
        name = request.POST.get('name')
        device_type = request.POST.get('device_type')
        status = request.POST.get('status')
        location = request.POST.get('location')
        purchase_date = request.POST.get('purchase_date')
        warranty_expiry_date = request.POST.get('warranty_expiry_date')
        description = request.POST.get('description')

        if not device_id_req or not name:
            messages.error(request, 'ID thiết bị và Tên thiết bị là bắt buộc.')
            # Cần trả về context để form có thể hiển thị lại với lỗi
            # Hoặc redirect về trang quản lý với thông báo lỗi
            return redirect(f"{reverse('admin_quan_ly_thiet_bi')}?error=missing_fields") 

        if Device.objects.filter(device_id=device_id_req).exists():
            messages.error(request, f'ID thiết bị "{device_id_req}" đã tồn tại.')
            return redirect(f"{reverse('admin_quan_ly_thiet_bi')}?error=duplicate_id&device_id={device_id_req}")

        try:
            Device.objects.create(
                device_id=device_id_req,
                name=name,
                device_type=device_type,
                status=status,
                location=location,
                purchase_date=purchase_date if purchase_date else None,
                warranty_expiry_date=warranty_expiry_date if warranty_expiry_date else None,
                description=description
            )
            messages.success(request, f'Thiết bị "{name}" đã được thêm thành công.')
            return redirect('admin_quan_ly_thiet_bi')
        except Exception as e:
            messages.error(request, f'Có lỗi xảy ra khi thêm thiết bị: {e}')
            return redirect(f"{reverse('admin_quan_ly_thiet_bi')}?error=exception")
    # Nếu là GET request, hoặc POST không thành công và không redirect ở trên,
    # có thể render một template riêng cho form thêm thiết bị hoặc xử lý trong template chính.
    # Hiện tại, logic thêm đang được xử lý trong modal của admin_quan_ly_thiet_bi.html
    # nên hàm này chủ yếu xử lý POST. Nếu muốn trang riêng, cần thay đổi.
    return redirect('admin_quan_ly_thiet_bi') # Mặc định redirect về trang quản lý

@staff_member_required
def admin_sua_thiet_bi(request, device_id):
    device_instance = get_object_or_404(Device, pk=device_id)
    if request.method == 'POST':
        # Lấy dữ liệu từ form
        device_instance.name = request.POST.get('name_edit', device_instance.name)
        device_instance.device_type = request.POST.get('device_type_edit', device_instance.device_type)
        device_instance.status = request.POST.get('status_edit', device_instance.status)
        device_instance.location = request.POST.get('location_edit', device_instance.location)
        purchase_date_str = request.POST.get('purchase_date_edit')
        device_instance.purchase_date = purchase_date_str if purchase_date_str else None
        warranty_expiry_date_str = request.POST.get('warranty_expiry_date_edit')
        device_instance.warranty_expiry_date = warranty_expiry_date_str if warranty_expiry_date_str else None
        device_instance.description = request.POST.get('description_edit', device_instance.description)
        
        try:
            device_instance.save()
            messages.success(request, f'Thiết bị "{device_instance.name}" đã được cập nhật thành công.')
            return redirect('admin_quan_ly_thiet_bi')
        except Exception as e:
            messages.error(request, f'Có lỗi xảy ra khi cập nhật thiết bị: {e}')
            # Nên redirect lại trang sửa với thông báo lỗi và dữ liệu đã nhập
            # return render(request, 'admin/admin_sua_thiet_bi_form.html', {'device': device_instance, 'error': str(e)})
            return redirect('admin_quan_ly_thiet_bi') # Tạm thời redirect về trang chính

    # Cho GET request, bạn sẽ muốn hiển thị form với dữ liệu hiện tại của thiết bị.
    # Điều này thường được xử lý bằng cách render một template form chỉnh sửa
    # hoặc truyền dữ liệu vào modal trong template admin_quan_ly_thiet_bi.html.
    # Ví dụ: return render(request, 'admin/admin_sua_thiet_bi_form.html', {'device': device_instance})
    # Hiện tại, chúng ta sẽ dựa vào modal, nên không cần render template riêng ở đây.
    # Logic lấy dữ liệu cho modal sẽ nằm trong admin_quan_ly_thiet_bi view hoặc AJAX.
    messages.info(request, f'Chức năng sửa thiết bị ID {device_id} đang được phát triển.')
    return redirect('admin_quan_ly_thiet_bi')

@staff_member_required
def admin_xoa_thiet_bi(request, device_id):
    device_instance = get_object_or_404(Device, pk=device_id)
    if request.method == 'POST': # Thường xóa sẽ dùng POST để an toàn
        try:
            device_name = device_instance.name
            device_instance.delete()
            messages.success(request, f'Thiết bị "{device_name}" đã được xóa thành công.')
        except Exception as e:
            messages.error(request, f'Có lỗi xảy ra khi xóa thiết bị: {e}')
        return redirect('admin_quan_ly_thiet_bi')
    
    # Cho GET request, có thể hiển thị trang xác nhận xóa.
    # Hoặc xử lý trực tiếp nếu không cần xác nhận (không khuyến khích)
    # Ví dụ: return render(request, 'admin/admin_xoa_thiet_bi_confirm.html', {'device': device_instance})
    messages.info(request, f'Chức năng xóa cho thiết bị ID {device_id} đang được phát triển (cần xác nhận POST).')
    return redirect('admin_quan_ly_thiet_bi')

@staff_member_required
def admin_quan_ly_nguoi_dung(request):
    users_list = User.objects.all().order_by('username')
    query = request.GET.get('q')
    role_filter = request.GET.get('role')
    status_filter = request.GET.get('status')

    if query:
        users_list = users_list.filter(
            Q(username__icontains=query) |
            Q(email__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query)
        ).distinct()

    if role_filter and role_filter != 'all':
        try:
            group = Group.objects.get(name=role_filter)
            users_list = users_list.filter(groups=group)
        except Group.DoesNotExist:
            messages.warning(request, f"Vai trò '{role_filter}' không tồn tại.")

    if status_filter and status_filter != 'all':
        users_list = users_list.filter(account_status=status_filter)

    items_per_page = request.GET.get('items_per_page', 10)
    paginator = Paginator(users_list, items_per_page)
    page = request.GET.get('page')

    try:
        users = paginator.page(page)
    except PageNotAnInteger:
        users = paginator.page(1)
    except EmptyPage:
        users = paginator.page(paginator.num_pages)
    
    # Ensure required groups exist
    required_roles = ['Admin', 'Manager', 'Maintenance Staff', 'Tenant']
    for role_name in required_roles:
        Group.objects.get_or_create(name=role_name)
    roles = Group.objects.all()

    context = {
        'users': users,
        'roles': roles,
        'account_status_choices': User.ACCOUNT_STATUS_CHOICES,
        'current_query': query or '',
        'current_role': role_filter or 'all',
        'current_status': status_filter or 'all',
        'items_per_page': int(items_per_page)
    }
    return render(request, 'admin/admin_quan_ly_nguoi_dung.html', context)

@staff_member_required
def admin_them_nguoi_dung(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        role_name = request.POST.get('role')
        department = request.POST.get('department')
        account_status = request.POST.get('status')

        if not username or not email or not password or not role_name or not account_status:
            messages.error(request, 'Vui lòng điền đầy đủ các trường bắt buộc.')
            from django.urls import reverse
            return redirect(f"{reverse('admin_quan_ly_nguoi_dung')}?action=add&form_errors=true")

        if User.objects.filter(username=username).exists():
            messages.error(request, f'Tên đăng nhập "{username}" đã tồn tại.')
            from django.urls import reverse
            return redirect(f"{reverse('admin_quan_ly_nguoi_dung')}?action=add&form_errors=true&username={username}&email={email}&role={role_name}&department={department}&status={account_status}")
        if User.objects.filter(email=email).exists():
            messages.error(request, f'Email "{email}" đã tồn tại.')
            from django.urls import reverse
            return redirect(f"{reverse('admin_quan_ly_nguoi_dung')}?action=add&form_errors=true&username={username}&email={email}&role={role_name}&department={department}&status={account_status}")

        try:
            user = User.objects.create_user(username=username, email=email, password=password)
            user.department = department
            user.account_status = account_status
            
            # Set is_staff and is_superuser based on role
            user.is_staff = role_name in ['Admin', 'Manager', 'Maintenance Staff'] 
            user.is_superuser = role_name == 'Admin'
            user.save() # Save to apply account_status logic which sets is_active

            # Ensure required groups exist and add user to group
            required_roles = ['Admin', 'Manager', 'Maintenance Staff', 'Tenant']
            for r_name in required_roles:
                Group.objects.get_or_create(name=r_name)
            
            group, created = Group.objects.get_or_create(name=role_name)
            user.groups.add(group)
            
            messages.success(request, f'Người dùng {user.username} đã được tạo thành công.')
            return redirect('admin_quan_ly_nguoi_dung')
        except Exception as e:
            messages.error(request, f'Có lỗi xảy ra khi thêm người dùng: {e}')
            from django.urls import reverse
            return redirect(f"{reverse('admin_quan_ly_nguoi_dung')}?action=add&form_errors=true&username={username}&email={email}&role={role_name}&department={department}&status={account_status}")
    return redirect('admin_quan_ly_nguoi_dung')

@staff_member_required
def admin_sua_nguoi_dung(request, user_id):
    user_instance = get_object_or_404(User, pk=user_id)
    if request.method == 'POST':
        new_username = request.POST.get('username_edit')
        new_email = request.POST.get('email_edit')
        new_first_name = request.POST.get('first_name_edit')
        new_last_name = request.POST.get('last_name_edit')
        new_department = request.POST.get('department_edit')
        new_account_status = request.POST.get('status_edit')
        new_role_name = request.POST.get('role_edit')

        # Validate username and email uniqueness if changed
        if new_username and new_username != user_instance.username and User.objects.filter(username=new_username).exclude(pk=user_id).exists():
            messages.error(request, f"Tên đăng nhập '{new_username}' đã tồn tại.")
            return redirect('admin_quan_ly_nguoi_dung') 
        if new_email and new_email != user_instance.email and User.objects.filter(email=new_email).exclude(pk=user_id).exists():
            messages.error(request, f"Email '{new_email}' đã tồn tại.")
            return redirect('admin_quan_ly_nguoi_dung')

        user_instance.username = new_username or user_instance.username
        user_instance.email = new_email or user_instance.email
        user_instance.first_name = new_first_name or user_instance.first_name
        user_instance.last_name = new_last_name or user_instance.last_name
        user_instance.department = new_department
        user_instance.account_status = new_account_status or user_instance.account_status

        # Update role
        if new_role_name:
            # Ensure required groups exist
            required_roles = ['Admin', 'Manager', 'Maintenance Staff', 'Tenant']
            for r_name in required_roles:
                Group.objects.get_or_create(name=r_name)
            try:
                group, created = Group.objects.get_or_create(name=new_role_name)
                user_instance.groups.clear()
                user_instance.groups.add(group)
                user_instance.is_staff = new_role_name in ['Admin', 'Manager', 'Maintenance Staff']
                user_instance.is_superuser = new_role_name == 'Admin'
            except Group.DoesNotExist:
                messages.warning(request, f"Vai trò '{new_role_name}' không tồn tại. Vai trò không được cập nhật.")
        
        user_instance.save() # This will also update is_active based on account_status
        messages.success(request, f'Thông tin người dùng {user_instance.username} đã được cập nhật.')
        return redirect('admin_quan_ly_nguoi_dung')
    
    return redirect('admin_quan_ly_nguoi_dung')

@staff_member_required
def admin_xoa_nguoi_dung(request, user_id):
    user_instance = get_object_or_404(User, pk=user_id)
    if request.user.id == user_instance.id:
        messages.error(request, "Bạn không thể xóa chính tài khoản của mình.")
        return redirect('admin_quan_ly_nguoi_dung')
        
    if request.method == 'POST': # Đảm bảo xóa qua POST
        try:
            username_deleted = user_instance.username
            user_instance.delete()
            messages.success(request, f'Người dùng {username_deleted} đã được xóa thành công.')
        except Exception as e:
            messages.error(request, f"Có lỗi xảy ra khi xóa người dùng: {e}")
    # Cho GET request, có thể hiển thị trang xác nhận xóa
    # context = {'user_to_delete': user_instance}
    # return render(request, 'admin/admin_xoa_nguoi_dung_confirm.html', context)
    return redirect('admin_quan_ly_nguoi_dung') # Tạm thời redirect

@staff_member_required
def admin_phieu_muon_bao_tri(request):
    from .models import MaintenanceRequest, User # Added User import
    requests_list = MaintenanceRequest.objects.all().order_by('-report_date')
    query = request.GET.get('q')
    status_filter = request.GET.get('status')

    if query:
        requests_list = requests_list.filter(
            Q(request_id__icontains=query) |
            Q(description__icontains=query) |
            Q(device__name__icontains=query) | 
            Q(device__device_id__icontains=query) |
            Q(reported_by__username__icontains=query)
        ).distinct()

    if status_filter and status_filter != 'all':
        requests_list = requests_list.filter(status=status_filter)

    items_per_page = request.GET.get('items_per_page', 10)
    paginator = Paginator(requests_list, items_per_page)
    page = request.GET.get('page')

    try:
        maintenance_requests = paginator.page(page)
    except PageNotAnInteger:
        maintenance_requests = paginator.page(1)
    except EmptyPage:
        maintenance_requests = paginator.page(paginator.num_pages)

    try:
        maintenance_staff_group = Group.objects.get(name='Maintenance Staff')
        maintenance_staff_list = User.objects.filter(groups=maintenance_staff_group, is_active=True).order_by('username')
    except Group.DoesNotExist:
        maintenance_staff_list = User.objects.none()
        messages.warning(request, "Nhóm 'Maintenance Staff' không được cấu hình trong hệ thống. Không thể tải danh sách nhân viên bảo trì.")
    except Exception as e:
        maintenance_staff_list = User.objects.none()
        messages.error(request, f"Lỗi khi truy vấn danh sách nhân viên bảo trì: {str(e)}")

    context = {
        'maintenance_requests': maintenance_requests,
        'status_choices': MaintenanceRequest.STATUS_CHOICES,
        'job_type_choices': MaintenanceRequest.JOB_TYPE_CHOICES, # Thêm lựa chọn công việc
        'current_query': query or '',
        'current_status': status_filter or 'all',
        'items_per_page': int(items_per_page),
        'devices': Device.objects.all(), 
        'maintenance_staff_list': maintenance_staff_list, # Danh sách nhân viên bảo trì đã lọc
    }
    return render(request, 'admin/admin_phieu_muon_bao_tri.html', context)

@staff_member_required
def admin_them_phieu_muon_bao_tri(request):
    if request.method == 'POST':
        device_id = request.POST.get('device_id')
        problem_description = request.POST.get('problem_description')
        job_type_val = request.POST.get('job_type')
        location_val = request.POST.get('location')
        priority = request.POST.get('priority', '3') # Default priority if not provided
        report_date_str = request.POST.get('report_date')
        assigned_to_user_id = request.POST.get('assigned_to_user_id')
        # maintenance_date_str = request.POST.get('maintenance_date') # Removed, field does not exist in model
        notes = request.POST.get('notes')

        if not problem_description or not report_date_str or not job_type_val or not location_val:
            messages.error(request, "Vui lòng điền đầy đủ các trường bắt buộc: Vị trí, Mô tả sự cố, Ngày báo cáo, Công việc.")
            return redirect('admin_phieu_muon_bao_tri')

        device_instance = None
        if device_id:
            try:
                device_instance = Device.objects.get(id=device_id)
            except Device.DoesNotExist:
                messages.error(request, "Thiết bị không tồn tại.")
                return redirect('admin_phieu_muon_bao_tri')

        assigned_to_instance = None
        if assigned_to_user_id:
            from .models import User as BmUser
            try:
                assigned_to_instance = BmUser.objects.get(id=assigned_to_user_id)
            except BmUser.DoesNotExist:
                messages.error(request, "Nhân viên bảo trì được chọn không hợp lệ.")
                return redirect('admin_phieu_muon_bao_tri')
        
        try:
            report_date = timezone.datetime.strptime(report_date_str, '%Y-%m-%d').date()
        except ValueError:
            messages.error(request, "Định dạng ngày báo cáo không hợp lệ. Vui lòng sử dụng YYYY-MM-DD.")
            return redirect('admin_phieu_muon_bao_tri')

        try:
            # Generate request_id
            today_str = timezone.now().strftime('%Y%m%d')
            prefix = f"REQ{today_str}"
            last_request_today = MaintenanceRequest.objects.filter(request_id__startswith=prefix).order_by('request_id').last()
            new_seq = 1
            if last_request_today:
                last_seq_str = last_request_today.request_id[len(prefix):]
                if last_seq_str.isdigit():
                    last_seq = int(last_seq_str)
                    new_seq = last_seq + 1
                else:
                    # Fallback if suffix is not purely numeric or format changed
                    new_seq = MaintenanceRequest.objects.filter(request_id__startswith=prefix).count() + 1
            
            generated_request_id = f"{prefix}{new_seq:03d}"
            # Ensure uniqueness, highly unlikely to loop more than once with this logic
            while MaintenanceRequest.objects.filter(request_id=generated_request_id).exists():
                new_seq += 1
                generated_request_id = f"{prefix}{new_seq:03d}"

            # Determine the reporter
            if not request.user.is_authenticated: # Check if user is authenticated
                logger.error("User is not authenticated during MaintenanceRequest creation.")
                messages.error(request, "Người dùng chưa đăng nhập để tạo yêu cầu.")
                return redirect('admin_phieu_muon_bao_tri')
            
            # If authenticated, request.user is the User instance
            from django.contrib.auth import get_user_model
            # Xác định người báo cáo (reported_by_user)
            reported_by_user = None
            if request.user.is_authenticated:
                    # UserModel = get_user_model() # Sẽ sử dụng User từ .models một cách trực tiếp
                try:
                    # Luôn lấy đối tượng User đầy đủ từ DB để tránh SimpleLazyObject
                    # User được import từ .models (tức là bmsync.models.User)
                    reported_by_user = User.objects.get(pk=request.user.pk)
                except User.DoesNotExist:
                    logger.error(f"Người dùng với pk={request.user.pk} không tồn tại khi tạo yêu cầu.")
                    messages.error(request, "Người dùng báo cáo không hợp lệ hoặc không tồn tại (mã lỗi UDF1).")
                    return redirect('admin_phieu_muon_bao_tri')
                except Exception as e: # Catch any other exception during user fetch
                    logger.error(f"Lỗi không xác định khi truy vấn người dùng báo cáo (pk={request.user.pk}): {e}", exc_info=True)
                    messages.error(request, "Có lỗi xảy ra khi xác thực người dùng báo cáo (mã lỗi UGE1).")
                    return redirect('admin_phieu_muon_bao_tri')
            else:
                messages.error(request, "Bạn cần đăng nhập để tạo yêu cầu.")
                return redirect('admin_phieu_muon_bao_tri') # Hoặc trang đăng nhập

            # Kiểm tra reported_by_user trước khi sử dụng
            if not reported_by_user:
                # This case implies user was not authenticated or DB fetch failed and message/redirect already handled.
                # If this is reached, it's an unexpected state, but the error message below is a safeguard.
                logger.error("Critical: reported_by_user is None after authentication checks and DB fetch attempt. This indicates a logic flaw or unhandled case.")
                messages.error(request, "Không thể xác định người dùng báo cáo cho yêu cầu (mã lỗi RFI3).")
                return redirect('admin_phieu_muon_bao_tri')
            new_request = MaintenanceRequest.objects.create(
                request_id=generated_request_id,
                device=device_instance,
                description=problem_description,
                job_type=job_type_val,
                location=location_val,
                priority=int(priority),
                reported_by=reported_by_user,
                report_date=report_date,
                assigned_to=assigned_to_instance,
                notes=notes,
                status='new' # Default status for new requests
            )
            messages.success(request, f"Yêu cầu '{new_request.request_id}' đã được tạo thành công.")

            # Tạo thông báo cho admin và staff
            try:
                admins_and_staff = User.objects.filter(Q(is_superuser=True) | Q(is_staff=True))
                for user_to_notify in admins_and_staff:
                    if user_to_notify != reported_by_user: # Không gửi thông báo cho người tự tạo yêu cầu
                        Notification.objects.create(
                            recipient=user_to_notify,
                            message=f"Có yêu cầu mới '{new_request.get_job_type_display()}' ({new_request.request_id}) từ người dùng {reported_by_user.username} cho thiết bị {new_request.device.name if new_request.device else 'N/A'} tại {new_request.location if new_request.location else 'N/A'}.",
                            notification_type='new_request',
                            related_object_id=new_request.pk
                        )
                # Thông báo cho người được giao việc (nếu có)
                if assigned_to_instance and assigned_to_instance != reported_by_user:
                     Notification.objects.create(
                        recipient=assigned_to_instance,
                        message=f"Bạn đã được giao một yêu cầu mới '{new_request.get_job_type_display()}' ({new_request.request_id}) cho thiết bị {new_request.device.name if new_request.device else 'N/A'} tại {new_request.location if new_request.location else 'N/A'}.",
                        notification_type='task_assigned',
                        related_object_id=new_request.pk
                    )

            except Exception as e_notif:
                logger.error(f"Lỗi khi tạo thông báo cho yêu cầu {new_request.request_id}: {e_notif}", exc_info=True)
                # Không nên để lỗi tạo thông báo làm hỏng luồng chính
                # messages.warning(request, "Yêu cầu đã được tạo nhưng có lỗi khi gửi thông báo.")

        except Exception as e:
            logger.error(f"Có lỗi xảy ra khi tạo yêu cầu bảo trì: {e}", exc_info=True)
            messages.error(request, f"Có lỗi xảy ra khi tạo yêu cầu: {e}. Vui lòng kiểm tra log hệ thống để biết thêm chi tiết.")
        
        return redirect('admin_phieu_muon_bao_tri')
    return redirect('admin_phieu_muon_bao_tri')

@staff_member_required
def admin_sua_phieu_muon_bao_tri(request, request_id): # Changed request_pk to request_id
    instance = get_object_or_404(MaintenanceRequest, request_id=request_id) # Changed request_id_str to request_id
    if request.method == 'POST':
        device_id = request.POST.get('device_id_edit')
        problem_description = request.POST.get('problem_description_edit', instance.description)
        job_type_val = request.POST.get('job_type_edit', instance.job_type)
        location_val = request.POST.get('location_edit', instance.location)
        priority_val = request.POST.get('priority_edit', str(instance.priority))
        report_date_str = request.POST.get('report_date_edit') # Generally report_date is not changed, but if it is:
        assigned_to_user_id = request.POST.get('assigned_to_user_id_edit')
        status_val = request.POST.get('status_edit', instance.status)
        notes = request.POST.get('notes_edit', instance.notes)
        completion_date_str = request.POST.get('completion_date_edit')

        if not problem_description or not job_type_val:
            messages.error(request, "Mô tả sự cố và Loại công việc là bắt buộc.")
            # Consider redirecting back to the edit form or page with an error
            return redirect('admin_phieu_muon_bao_tri')

        device_instance = instance.device # Keep current device if not changed
        if device_id:
            try:
                device_instance = Device.objects.get(id=device_id)
            except Device.DoesNotExist:
                messages.error(request, "Thiết bị được chọn không tồn tại.")
                return redirect('admin_phieu_muon_bao_tri') # Or back to edit page

        assigned_to_instance = instance.assigned_to # Keep current if not changed
        if assigned_to_user_id:
            if assigned_to_user_id == "__clear__": # Option to clear assignee
                assigned_to_instance = None
            else:
                try:
                    assigned_to_instance = User.objects.get(id=assigned_to_user_id)
                except User.DoesNotExist:
                    messages.error(request, "Nhân viên bảo trì được chọn không hợp lệ.")
                    return redirect('admin_phieu_muon_bao_tri') # Or back to edit page
        elif assigned_to_user_id == "": # If submitted as empty, treat as clear
             assigned_to_instance = None

        try:
            if report_date_str:
                instance.report_date = timezone.datetime.strptime(report_date_str, '%Y-%m-%d').date()
            
            # Handle completion_date from <input type="date"> which submits 'YYYY-MM-DD'
            if 'completion_date_edit' in request.POST: # Check if the field was part of the submission
                if completion_date_str: # If a date string is provided (e.g., "2023-10-26")
                    parsed_completion_date_obj = timezone.datetime.strptime(completion_date_str, '%Y-%m-%d').date()
                    # Assuming MaintenanceRequest.completion_date is a DateTimeField.
                    # Set to the beginning of the day for the given date.
                    instance.completion_date = timezone.make_aware(
                        timezone.datetime.combine(parsed_completion_date_obj, timezone.datetime.min.time())
                    )
                else: # If the field was submitted but empty (completion_date_str is '')
                    instance.completion_date = None
            # If 'completion_date_edit' was not in request.POST, instance.completion_date remains unchanged by this block.

        except ValueError:
            # This error message covers parsing if they use YYYY-MM-DD
            messages.error(request, "Định dạng ngày không hợp lệ. Vui lòng sử dụng định dạng YYYY-MM-DD.")
            return redirect('admin_phieu_muon_bao_tri') # Or back to edit page

        instance.device = device_instance
        instance.description = problem_description
        instance.job_type = job_type_val
        instance.location = location_val
        instance.priority = int(priority_val) if priority_val else 3
        instance.assigned_to = assigned_to_instance
        instance.status = status_val
        instance.notes = notes
        # instance.reported_by is not changed here as it's the original reporter

        original_assigned_to = MaintenanceRequest.objects.get(pk=instance.pk).assigned_to
        original_status = MaintenanceRequest.objects.get(pk=instance.pk).status

        try:
            instance.save() # Lưu các thay đổi vào instance
            messages.success(request, f"Yêu cầu '{instance.request_id}' đã được cập nhật thành công.")

            # Logic tạo thông báo sau khi cập nhật thành công
            try:
                # 1. Thông báo thay đổi người được giao
                new_assigned_to = instance.assigned_to
                if original_assigned_to != new_assigned_to:
                    if new_assigned_to and new_assigned_to != instance.reported_by:
                        Notification.objects.create(
                            recipient=new_assigned_to,
                            message=f"Bạn vừa được giao yêu cầu '{instance.get_job_type_display()}' ({instance.request_id}) cho thiết bị {instance.device.name if instance.device else 'N/A'} tại {instance.location if instance.location else 'N/A'}.",
                            notification_type='task_assigned',
                            related_object_id=instance.pk
                        )
                    if original_assigned_to and original_assigned_to != instance.reported_by:
                        Notification.objects.create(
                            recipient=original_assigned_to,
                            message=f"Yêu cầu '{instance.get_job_type_display()}' ({instance.request_id}) không còn được giao cho bạn nữa.",
                            notification_type='task_assigned', # Có thể tạo loại 'task_unassigned' nếu cần
                            related_object_id=instance.pk
                        )

                # 2. Thông báo thay đổi trạng thái
                new_status = instance.status
                if original_status != new_status:
                    notification_type_for_status_change = 'request_processed'
                    if new_status == 'completed': # 'completed' là key cho trạng thái Hoàn thành
                        notification_type_for_status_change = 'task_completed'
                    
                    # Thông báo cho người báo cáo
                    if instance.reported_by:
                        Notification.objects.create(
                            recipient=instance.reported_by,
                            message=f"Yêu cầu '{instance.get_job_type_display()}' ({instance.request_id}) của bạn đã được cập nhật trạng thái thành '{instance.get_status_display()}'.",
                            notification_type=notification_type_for_status_change,
                            related_object_id=instance.pk
                        )
                    # Thông báo cho người được giao (nếu có và khác người báo cáo)
                    # new_assigned_to được định nghĩa ở khối trên là instance.assigned_to
                    if new_assigned_to and new_assigned_to != instance.reported_by:
                        Notification.objects.create(
                            recipient=new_assigned_to,
                            message=f"Yêu cầu '{instance.get_job_type_display()}' ({instance.request_id}) bạn đang xử lý đã được cập nhật trạng thái thành '{instance.get_status_display()}'.",
                            notification_type=notification_type_for_status_change,
                            related_object_id=instance.pk
                        )
            except Exception as e_notif_update:
                logger.error(f"Lỗi khi tạo thông báo cập nhật cho yêu cầu {instance.request_id}: {e_notif_update}", exc_info=True)

        except Exception as e:
            messages.error(request, f"Có lỗi xảy ra khi cập nhật yêu cầu: {e}")
        
        return redirect('admin_phieu_muon_bao_tri')

    # For GET request, this view might not be directly called if using modals.
    # If it were, you'd pass the instance and choices to a template.
    # messages.info(request, "Chức năng sửa phiếu đang được xử lý qua modal.")
    return redirect('admin_phieu_muon_bao_tri') # Redirect if accessed via GET unexpectedly

@staff_member_required
def admin_xoa_phieu_muon_bao_tri(request, request_id): # Changed request_id_str to request_id
    instance = get_object_or_404(MaintenanceRequest, request_id=request_id) # Changed request_id_str to request_id
    if request.method == 'POST': # Đảm bảo xóa qua POST
        try:
            req_id_deleted = instance.request_id # Corrected from maintenance_req to instance
            instance.delete() # Corrected from maintenance_req to instance
            messages.success(request, f'Yêu cầu "{req_id_deleted}" đã được xóa.')
        except Exception as e:
            messages.error(request, f'Có lỗi xảy ra khi xóa yêu cầu: {e}')
    return redirect('admin_phieu_muon_bao_tri')

@staff_member_required
def send_maintenance_notification(request, request_id):
    maintenance_request_item = get_object_or_404(MaintenanceRequest, request_id=request_id)

    if maintenance_request_item.notification_status == 'sent' and request.method == 'GET': # Allow re-sending if explicitly POSTed again, but show info on GET
        messages.info(request, f"Thông báo cho yêu cầu {maintenance_request_item.request_id} đã được gửi trước đó. Bạn có muốn gửi lại không?")
        # We will proceed if it's a POST request, effectively allowing a resend.
        # If it's a GET, we just inform and redirect.
        if request.method == 'GET':
            return redirect('admin_phieu_muon_bao_tri')

    if request.method == 'POST':
        try:
            collected_recipients_info = {} # Store user and their role

            # 1. Reporter (Tenant)
            if maintenance_request_item.reported_by:
                if maintenance_request_item.reported_by not in collected_recipients_info:
                    collected_recipients_info[maintenance_request_item.reported_by] = 'Tenant'

            # 2. Assigned Staff (Maintenance Staff)
            if maintenance_request_item.assigned_to:
                if maintenance_request_item.assigned_to not in collected_recipients_info:
                     collected_recipients_info[maintenance_request_item.assigned_to] = 'Maintenance Staff (Assigned)'
                else: # If reporter is also assignee, prioritize assignee role for this context
                    if collected_recipients_info[maintenance_request_item.assigned_to] == 'Tenant':
                        collected_recipients_info[maintenance_request_item.assigned_to] = 'Maintenance Staff (Assigned)'

            # 3. Admins (Superusers or users in 'Admin' group)
            admin_users = User.objects.filter(Q(is_superuser=True) | Q(groups__name__in=['Admin', 'SystemAdmin']), is_active=True).distinct()
            for user in admin_users:
                if user not in collected_recipients_info:
                    collected_recipients_info[user] = 'Admin'

            # 4. Managers (Users in 'Manager' group)
            manager_users = User.objects.filter(groups__name='Manager', is_active=True).distinct()
            for user in manager_users:
                if user not in collected_recipients_info:
                    collected_recipients_info[user] = 'Manager'
            
            # 5. Other Maintenance Staff (Users in 'Maintenance Staff' group, not already assigned)
            # This ensures general staff are notified if they aren't the direct assignee but part of the team
            general_maintenance_staff = User.objects.filter(groups__name='Maintenance Staff', is_active=True).exclude(id=maintenance_request_item.assigned_to_id if maintenance_request_item.assigned_to else None).distinct()
            for user in general_maintenance_staff:
                if user not in collected_recipients_info:
                    collected_recipients_info[user] = 'Maintenance Staff (General)'

            # Prepare common request details
            req_id = maintenance_request_item.request_id
            req_type_display = maintenance_request_item.get_job_type_display().lower()
            req_device_name = maintenance_request_item.device.name if maintenance_request_item.device else "Không có thiết bị cụ thể"
            req_location_name = maintenance_request_item.location if maintenance_request_item.location else "Không có vị trí cụ thể"
            req_status_display = maintenance_request_item.get_status_display()
            req_description_text = maintenance_request_item.description
            reporter_username = maintenance_request_item.reported_by.username if maintenance_request_item.reported_by else "N/A"
            assignee_username = maintenance_request_item.assigned_to.username if maintenance_request_item.assigned_to else "Chưa giao"
            report_date_formatted = maintenance_request_item.report_date.strftime('%d/%m/%Y %H:%M')
            completion_date_formatted = maintenance_request_item.completion_date.strftime('%d/%m/%Y %H:%M') if maintenance_request_item.completion_date else "Chưa hoàn thành"

            base_email_info = (
                f"ID Yêu cầu: {req_id}\n"
                f"Loại công việc: {req_type_display}\n"
                f"Thiết bị: {req_device_name}\n"
                f"Vị trí: {req_location_name}\n"
                f"Ngày báo cáo: {report_date_formatted}\n"
                f"Trạng thái hiện tại: {req_status_display}\n"
                f"Mô tả: {req_description_text}\n"
            )

            emails_sent_count = 0
            notifications_created_count = 0

            for user_recipient, role_detail in collected_recipients_info.items():
                if not user_recipient or not user_recipient.is_active or not user_recipient.email:
                    logger.warning(f"Skipping notification for user {user_recipient.username if user_recipient else 'Unknown'} due to missing email, inactivity, or null user.")
                    continue

                email_subject_user = f"[BMSync] Cập nhật Yêu cầu {req_id}: {req_type_display} - {req_status_display}"
                message_for_user_email_lines = []
                message_for_in_app_notification = ""

                greeting = f"Chào {user_recipient.first_name or user_recipient.username},"
                closing = "Trân trọng,\nĐội ngũ BMSync."

                # Common details for most roles
                common_details_for_email = (
                    f"{base_email_info}"
                    f"Người báo cáo: {reporter_username}\n"
                    f"Người xử lý: {assignee_username}\n"
                    f"Ngày hoàn thành dự kiến/thực tế: {completion_date_formatted}\n"
                )

                if role_detail == "Admin":
                    message_for_user_email_lines = [
                        greeting,
                        f"Hệ thống BMSync thông báo cập nhật toàn diện về yêu cầu {req_type_display} (ID: {req_id}):",
                        common_details_for_email,
                        "Bạn có toàn quyền xem xét và quản lý yêu cầu này.",
                        closing
                    ]
                    message_for_in_app_notification = f"Ycầu {req_id} ({req_type_display}) tại {req_location_name} cập nhật: {req_status_display}. Báo cáo: {reporter_username}, Xử lý: {assignee_username}."

                elif role_detail == "Manager":
                    message_for_user_email_lines = [
                        greeting,
                        f"Thông tin cập nhật về yêu cầu {req_type_display} (ID: {req_id}) trong phạm vi quản lý của bạn:",
                        common_details_for_email,
                        "Vui lòng theo dõi và điều phối nếu cần.",
                        closing
                    ]
                    message_for_in_app_notification = f"Ycầu {req_id} ({req_type_display}) tại {req_location_name} (quản lý) cập nhật: {req_status_display}. Xử lý: {assignee_username}."

                elif role_detail == "Maintenance Staff (Assigned)":
                    message_for_user_email_lines = [
                        greeting,
                        f"Yêu cầu {req_type_display} (ID: {req_id}) được giao cho bạn đã có cập nhật:",
                        common_details_for_email,
                        "Xin hãy kiểm tra và thực hiện công việc theo lịch trình. Cập nhật trạng thái khi hoàn thành.",
                        closing
                    ]
                    message_for_in_app_notification = f"Ycầu {req_id} ({req_type_display}) bạn xử lý tại {req_location_name} cập nhật: {req_status_display}."
                
                elif role_detail == "Maintenance Staff (General)":
                    message_for_user_email_lines = [
                        greeting,
                        f"Thông tin về yêu cầu {req_type_display} (ID: {req_id}) trong hệ thống có thể bạn quan tâm:",
                        common_details_for_email,
                        "Thông tin này được gửi cho bạn với vai trò nhân viên bảo trì trong đội.",
                        closing
                    ]
                    message_for_in_app_notification = f"Ycầu {req_id} ({req_type_display}) tại {req_location_name} (Xử lý: {assignee_username}) cập nhật: {req_status_display}."

                elif role_detail == "Tenant": # This is the reporter
                    message_for_user_email_lines = [
                        greeting,
                        f"Yêu cầu {req_type_display} (ID: {req_id}) của bạn đã được cập nhật:",
                        base_email_info, # Reporter might not need to see who reported it again
                        f"Người xử lý: {assignee_username}\n",
                        f"Ngày hoàn thành dự kiến/thực tế: {completion_date_formatted}\n",
                        "Bạn có thể theo dõi tiến trình trong hệ thống BMSync.",
                        closing
                    ]
                    message_for_in_app_notification = f"Ycầu {req_id} ({req_type_display}) của bạn tại {req_location_name} cập nhật: {req_status_display}."
                
                else: # Fallback for any other roles or unclassified
                    logger.warning(f"User {user_recipient.username} has an unhandled role: {role_detail} for request {req_id}. Sending generic notification.")
                    message_for_user_email_lines = [
                        greeting,
                        f"Thông báo cập nhật về yêu cầu {req_type_display} (ID: {req_id}):",
                        common_details_for_email,
                        closing
                    ]
                    message_for_in_app_notification = f"Ycầu {req_id} ({req_type_display}) tại {req_location_name} cập nhật: {req_status_display}."

                # Create In-App Notification
                if message_for_in_app_notification:
                    Notification.objects.create(
                        recipient=user_recipient,
                        message=message_for_in_app_notification,
                        notification_type='request_processed', # Consider making this more dynamic based on status
                        related_object_id=maintenance_request_item.id
                    )
                    notifications_created_count += 1

                # Send Email
                if message_for_user_email_lines:
                    email_body = "\n\n".join(message_for_user_email_lines)
                    try:
                        send_mail(
                            email_subject_user,
                            email_body,
                            settings.DEFAULT_FROM_EMAIL if hasattr(settings, 'DEFAULT_FROM_EMAIL') else 'noreply@bmsync.com',
                            [user_recipient.email],
                            fail_silently=False,
                        )
                        emails_sent_count += 1
                        logger.info(f"Email sent to {user_recipient.email} for request {req_id} (Role: {role_detail})")
                    except Exception as mail_exc:
                        logger.error(f"Lỗi gửi email cho {user_recipient.email} (request {req_id}): {mail_exc}", exc_info=True)
                        messages.warning(request, f"Lỗi gửi email đến {user_recipient.email}. Thông báo trong hệ thống đã được tạo.")
            
            if emails_sent_count > 0 or notifications_created_count > 0:
                maintenance_request_item.notification_status = 'sent'
                maintenance_request_item.save(update_fields=['notification_status', 'updated_at'])
                messages.success(request, f"Đã xử lý gửi {emails_sent_count} email và tạo {notifications_created_count} thông báo cho yêu cầu {req_id}.")
            else:
                messages.info(request, f"Không có người nhận hợp lệ nào được tìm thấy để gửi thông báo cho yêu cầu {req_id}.")

        except Exception as e:
            logger.error(f"Lỗi nghiêm trọng khi xử lý thông báo cho yêu cầu {maintenance_request_item.request_id}: {e}", exc_info=True)
            messages.error(request, f"Có lỗi xảy ra khi gửi thông báo: {e}. Vui lòng kiểm tra logs.")
        return redirect('admin_phieu_muon_bao_tri')
    else:
        messages.error(request, "Phương thức không hợp lệ để gửi thông báo.")
        return redirect('admin_phieu_muon_bao_tri')

@staff_member_required
def admin_tong_hop_bao_cao(request):
    return render(request, 'admin/admin_tong_hop_bao_cao.html')

@staff_member_required
def admin_chatbot(request):
    return render(request, 'admin/admin_chatbot.html')

from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from .models import Notification # Đảm bảo import Notification model
from django.http import JsonResponse
from django.views.decorators.http import require_POST

@staff_member_required
def admin_thong_bao(request):
    User = get_user_model()
    # Lấy thông báo cho người dùng hiện tại
    # Đảm bảo rằng Notification model đã được import ở đầu file: from .models import Notification
    try:
        # Sửa lỗi ở đây: sử dụng request.user trực tiếp
        notifications_list = Notification.objects.filter(recipient=request.user).order_by('-timestamp')
        
        status_filter = request.GET.get('status', 'all') # 'all', 'unread', 'read'
        if status_filter == 'unread':
            notifications_list = notifications_list.filter(is_read=False)
        elif status_filter == 'read':
            notifications_list = notifications_list.filter(is_read=True)

        items_per_page = request.GET.get('items_per_page', 10)
        paginator = Paginator(notifications_list, items_per_page)
        page = request.GET.get('page')

        try:
            notifications = paginator.page(page)
        except PageNotAnInteger:
            notifications = paginator.page(1)
        except EmptyPage:
            notifications = paginator.page(paginator.num_pages)

        context = {
            'notifications': notifications,
            'current_status': status_filter,
            'items_per_page': int(items_per_page),
            'total_unread': Notification.objects.filter(recipient=request.user, is_read=False).count()
        }
        return render(request, 'admin/admin_thong_bao.html', context)
    except Exception as e:
        messages.error(request, f"Đã có lỗi xảy ra khi tải trang thông báo: {e}")
        # Ghi log lỗi ở đây nếu cần
        # logger.error(f"Error in admin_thong_bao for user {request.user.username}: {e}")
        # Có thể redirect về trang chủ hoặc dashboard nếu trang thông báo không thể hiển thị
        return redirect('admin_dashboard') # Hoặc một trang lỗi thân thiện hơn

@staff_member_required
def mark_notification_as_read(request, notification_id):
    try:
        notification = Notification.objects.get(id=notification_id, recipient=request.user)
        if not notification.is_read:
            notification.is_read = True
            notification.save()
        return JsonResponse({'success': True})
    except Notification.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Notification not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@staff_member_required
@require_POST
def mark_all_notifications_as_read(request):
    try:
        Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@staff_member_required
def admin_bao_mat(request):
    return render(request, 'admin/admin_bao_mat.html')

@staff_member_required
def admin_cai_dat(request):
    return render(request, 'admin/admin_cai_dat.html')

@staff_member_required
def admin_ho_tro(request):
    return render(request, 'admin/admin_ho_tro.html')

@staff_member_required
def admin_change_password(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # Quan trọng để không bị logout sau khi đổi pass
            messages.success(request, 'Mật khẩu của bạn đã được thay đổi thành công!')
            return redirect('admin_bao_mat')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field.capitalize()}: {error}")
            # Không redirect ở đây để form hiển thị lỗi trên trang bảo mật
            # return render(request, 'admin/admin_bao_mat.html', {'password_change_form': form})
            # Thay vào đó, ta sẽ redirect và dựa vào messages để hiển thị lỗi
            return redirect('admin_bao_mat') # Hoặc render lại trang với context lỗi
    # Nếu là GET request hoặc form không valid và không redirect, có thể render lại trang với form trống
    # Hoặc đơn giản là redirect về trang bảo mật, vì form đã có sẵn trên template
    return redirect('admin_bao_mat')

@staff_member_required
def admin_logout_other_devices(request):
    if request.method == 'POST':
        try:
            current_session_key = request.session.session_key
            # Lấy tất cả các session của user hiện tại, ngoại trừ session hiện tại
            # User.sessions.all() không phải là một API chuẩn của Django.
            # Chúng ta cần query trực tiếp model Session.
            user_sessions = Session.objects.filter(expire_date__gte=timezone.now())
            deleted_count = 0
            for session in user_sessions:
                session_data = session.get_decoded()
                # Kiểm tra xem session có thuộc về user hiện tại không và không phải là session hiện tại
                if session_data.get('_auth_user_id') == str(request.user.id) and session.session_key != current_session_key:
                    session.delete()
                    deleted_count += 1
            
            if deleted_count > 0:
                messages.success(request, f'Đã đăng xuất thành công khỏi {deleted_count} thiết bị khác.')
            else:
                messages.info(request, 'Không có phiên đăng nhập nào khác để đăng xuất.')
        except Exception as e:
            messages.error(request, f'Có lỗi xảy ra: {e}')
        return redirect('admin_bao_mat')
    return redirect('admin_bao_mat')

@login_required
@require_http_methods(["POST"])
def send_message(request):
    try:
        # Validate request body
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON format'}, status=400)

        message = data.get('message')
        role = data.get('role')

        if not message:
            return JsonResponse({'error': 'Message is required'}, status=400)

        if not role:
            return JsonResponse({'error': 'Role is required'}, status=400)

        if role not in ['manager', 'user', 'tenant', 'maintenance']:
            return JsonResponse({'error': 'Invalid role'}, status=400)

        # Get API key from settings
        api_key = getattr(settings, 'GEMINI_API_KEY', None)
        if not api_key:
            logger.error("Gemini API key not configured")
            return JsonResponse({'error': 'Chat service configuration error'}, status=500)

        # Prepare system prompt based on role
        if role == 'manager':
            # Import models at the beginning of the function to avoid scope issues
            from .models import Device, MaintenanceRequest, Notification
            
            try:
                # Gather manager context data
                user = request.user
                total_devices = Device.objects.count()
                active_devices = Device.objects.filter(status='active').count()
                pending_maintenance = MaintenanceRequest.objects.filter(status__in=['new', 'pending']).count()
                completed_maintenance = MaintenanceRequest.objects.filter(status='completed').count()

                # Get detailed device information
                devices = Device.objects.all()
                device_list = []
                for device in devices:
                    device_info = {
                        'id': device.device_id,
                        'name': device.name,
                        'type': device.device_type,
                        'status': device.status,
                        'location': device.location,
                        'last_maintenance': device.last_maintenance_date.strftime('%d/%m/%Y') if device.last_maintenance_date else 'Chưa có',
                        'next_maintenance': device.next_maintenance_date.strftime('%d/%m/%Y') if device.next_maintenance_date else 'Chưa lên lịch'
                    }
                    device_list.append(device_info)

                # Format device list as text
                devices_text = "Danh sách thiết bị:\n"
                for device in device_list:
                    devices_text += f"""
                        - ID: {device['id']}
                            Tên: {device['name']}
                            Loại: {device['type']}
                            Trạng thái: {device['status']}
                            Vị trí: {device['location']}
                            Bảo trì gần nhất: {device['last_maintenance']}
                            Bảo trì tiếp theo: {device['next_maintenance']}
                    """

                system_prompt = f"""Bạn là BMSync Manager Assistant, một chatbot AI cho quản lý hệ thống BMSync.

                Thông tin về Manager hiện tại:
                - Tên: {user.get_full_name() or user.username}
                - Username: {user.username}
                - Email: {user.email}

                Thông tin hệ thống:
                - Tổng số thiết bị: {total_devices}
                - Thiết bị đang hoạt động: {active_devices}
                - Yêu cầu bảo trì đang chờ: {pending_maintenance}
                - Yêu cầu bảo trì đã hoàn thành: {completed_maintenance}

                {devices_text}

                Quyền hạn của Manager:
                - Quản lý và giám sát toàn bộ thiết bị trong hệ thống
                - Phê duyệt yêu cầu thêm/sửa/xóa thiết bị
                - Xem báo cáo và thống kê về hiệu suất thiết bị
                - Quản lý yêu cầu bảo trì và sự cố
                - Tạo và xem báo cáo phân tích

                Hãy trả lời câu hỏi sau của Manager một cách chuyên nghiệp và hữu ích, sử dụng thông tin context ở trên. Nếu được hỏi về thiết bị, hãy trả lời chi tiết dựa trên danh sách thiết bị đã cung cấp:"""
            except Exception as manager_error:
                logger.error(f"Error preparing manager context: {str(manager_error)}")
                system_prompt = """Bạn là BMSync Manager Assistant, một chatbot AI cho quản lý hệ thống BMSync.

                Xin lỗi, tôi không thể truy cập dữ liệu hệ thống lúc này. Tôi sẽ cố gắng trả lời câu hỏi của bạn dựa trên kiến thức chung về quản lý tòa nhà.

                Hãy trả lời câu hỏi sau của Manager một cách chuyên nghiệp và hữu ích:"""
        elif role == 'tenant':
            try:
                # Gather tenant context data
                user = request.user
                user_profile = user.profile
                
                # Get tenant's devices
                from dashboard.models import Device, MaintenanceRequest, MaintenanceTask
                
                devices = Device.objects.filter(tenant=user_profile)
                maintenance_requests = MaintenanceRequest.objects.filter(requester=user_profile)
                completed_tasks = MaintenanceTask.objects.filter(
                    maintenance_request__requester=user_profile, 
                    status='completed'
                )
                
                # Format device list as text
                devices_text = "Danh sách thiết bị của bạn:\n"
                for i, device in enumerate(devices, 1):
                    device_type_display = device.get_device_type_display()
                    status_display = device.get_status_display()
                    devices_text += f"""
                        {i}. {device.name}
                           - Loại: {device_type_display}
                           - Vị trí: {device.location}
                           - Trạng thái: {status_display}
                           - Cập nhật: {device.last_updated.strftime('%d/%m/%Y') if device.last_updated else 'Chưa cập nhật'}
                    """
                
                # Format maintenance requests as text
                requests_text = "Danh sách yêu cầu bảo trì của bạn:\n"
                for i, req in enumerate(maintenance_requests, 1):
                    device_name = req.device.name if req.device else "N/A"
                    status_display = req.get_status_display()
                    priority_display = req.get_priority_display()
                    created_at = req.created_at.strftime("%d/%m/%Y")
                    requests_text += f"""
                        {i}. {req.title}
                           - Thiết bị: {device_name}
                           - Trạng thái: {status_display}
                           - Ưu tiên: {priority_display}
                           - Ngày tạo: {created_at}
                    """
                    
                # Format completed tasks as text
                completed_text = "Lịch sử công việc bảo trì đã hoàn thành:\n"
                for i, task in enumerate(completed_tasks, 1):
                    device_name = task.maintenance_request.device.name if task.maintenance_request.device else "N/A"
                    due_date = task.due_date.strftime("%d/%m/%Y")
                    assigned_to = task.assigned_to.user.get_full_name() if task.assigned_to else "N/A"
                    rating = f"{task.rating}/5" if task.rating else "Chưa đánh giá"
                    completed_text += f"""
                        {i}. {task.title}
                           - Thiết bị: {device_name}
                           - Ngày hoàn thành: {due_date}
                           - Nhân viên: {assigned_to}
                           - Đánh giá: {rating}
                    """
                
                system_prompt = f"""Bạn là BMSync Tenant Assistant, một chatbot AI hỗ trợ người thuê trong hệ thống BMSync.

                Thông tin về Tenant hiện tại:
                - Tên: {user.get_full_name() or user.username}
                - Username: {user.username}
                - Email: {user.email}

                Thông tin tổng quan:
                - Tổng số thiết bị: {devices.count()}
                - Tổng số yêu cầu bảo trì: {maintenance_requests.count()}
                - Yêu cầu đã hoàn thành: {completed_tasks.count()}

                {devices_text}

                {requests_text}

                {completed_text}

                Quyền hạn của Tenant:
                - Xem thông tin thiết bị của mình
                - Tạo yêu cầu bảo trì cho thiết bị
                - Theo dõi trạng thái yêu cầu bảo trì
                - Xem lịch sử bảo trì
                - Đánh giá công việc bảo trì đã hoàn thành

                Hãy trả lời câu hỏi sau của Tenant một cách thân thiện và hữu ích, sử dụng thông tin context ở trên. Nếu được hỏi về thiết bị hoặc yêu cầu bảo trì, hãy trả lời chi tiết dựa trên danh sách đã cung cấp. Hãy sử dụng Markdown để định dạng câu trả lời cho dễ đọc:"""
            except Exception as tenant_error:
                logger.error(f"Error preparing tenant context: {str(tenant_error)}")
                system_prompt = """Bạn là BMSync Tenant Assistant, một chatbot AI hỗ trợ người thuê trong hệ thống BMSync.

                Xin lỗi, tôi không thể truy cập dữ liệu của bạn lúc này. Tôi sẽ cố gắng trả lời câu hỏi của bạn dựa trên kiến thức chung về quản lý tòa nhà.

                Hãy trả lời câu hỏi sau của Tenant một cách thân thiện và hữu ích:"""
        elif role == 'maintenance':
            try:
                # Gather maintenance staff context data
                user = request.user
                user_profile = user.profile
                
                # Import models for maintenance staff
                from dashboard.models import MaintenanceTask, MaintenanceRequest, Device
                
                # Get maintenance tasks assigned to this user
                maintenance_tasks = MaintenanceTask.objects.filter(assigned_to=user_profile)
                pending_tasks = maintenance_tasks.filter(status='pending').count()
                in_progress_tasks = maintenance_tasks.filter(status='in_progress').count()
                completed_tasks = maintenance_tasks.filter(status='completed').count()
                total_tasks = maintenance_tasks.count()
                
                # Format tasks as text
                tasks_text = "Danh sách công việc của bạn:\n"
                for i, task in enumerate(maintenance_tasks.order_by('status', 'due_date')[:10], 1):
                    device_name = task.maintenance_request.device.name if task.maintenance_request and task.maintenance_request.device else "N/A"
                    status_display = task.get_status_display()
                    due_date = task.due_date.strftime("%d/%m/%Y") if task.due_date else "Không có hạn"
                    progress = f"{task.progress}%" if task.progress is not None else "0%"
                    
                    tasks_text += f"""
                        {i}. {task.title}
                           - Thiết bị: {device_name}
                           - Trạng thái: {status_display}
                           - Hạn hoàn thành: {due_date}
                           - Tiến độ: {progress}
                    """
                
                # Get recent completed tasks
                recent_completed = maintenance_tasks.filter(status='completed').order_by('-updated_at')[:5]
                completed_text = "Công việc gần đây đã hoàn thành:\n"
                for i, task in enumerate(recent_completed, 1):
                    device_name = task.maintenance_request.device.name if task.maintenance_request and task.maintenance_request.device else "N/A"
                    completion_date = task.updated_at.strftime("%d/%m/%Y")
                    
                    completed_text += f"""
                        {i}. {task.title}
                           - Thiết bị: {device_name}
                           - Hoàn thành ngày: {completion_date}
                    """
                
                # Get pending tasks that need attention
                urgent_tasks = maintenance_tasks.filter(status='pending', maintenance_request__priority__in=[1, 2]).order_by('due_date')[:5]
                urgent_text = "Công việc ưu tiên cần xử lý:\n"
                if urgent_tasks:
                    for i, task in enumerate(urgent_tasks, 1):
                        device_name = task.maintenance_request.device.name if task.maintenance_request and task.maintenance_request.device else "N/A"
                        priority = task.maintenance_request.get_priority_display() if task.maintenance_request else "N/A"
                        due_date = task.due_date.strftime("%d/%m/%Y") if task.due_date else "Không có hạn"
                        
                        urgent_text += f"""
                            {i}. {task.title}
                               - Thiết bị: {device_name}
                               - Độ ưu tiên: {priority}
                               - Hạn hoàn thành: {due_date}
                        """
                else:
                    urgent_text += "Không có công việc ưu tiên cần xử lý ngay.\n"
                
                system_prompt = f"""Bạn là BMSync Maintenance Assistant, một chatbot AI hỗ trợ nhân viên kỹ thuật trong hệ thống BMSync.

                Thông tin về Nhân viên kỹ thuật hiện tại:
                - Tên: {user.get_full_name() or user.username}
                - Username: {user.username}
                - Email: {user.email}

                Thông tin tổng quan công việc:
                - Tổng số công việc: {total_tasks}
                - Công việc mới: {pending_tasks}
                - Công việc đang xử lý: {in_progress_tasks}
                - Công việc đã hoàn thành: {completed_tasks}

                {tasks_text}

                {urgent_text}

                {completed_text}

                Quyền hạn của Nhân viên kỹ thuật:
                - Xem danh sách công việc được giao
                - Cập nhật trạng thái và tiến độ công việc
                - Báo cáo kết quả bảo trì
                - Xem lịch sử bảo trì đã thực hiện
                - Nhận thông báo về công việc mới và ưu tiên

                Hãy trả lời câu hỏi sau của Nhân viên kỹ thuật một cách chuyên nghiệp và hữu ích, sử dụng thông tin context ở trên. Nếu được hỏi về công việc hoặc thiết bị, hãy trả lời chi tiết dựa trên danh sách đã cung cấp. Hãy sử dụng Markdown để định dạng câu trả lời cho dễ đọc:"""
            except Exception as maintenance_error:
                logger.error(f"Error preparing maintenance context: {str(maintenance_error)}")
                system_prompt = """Bạn là BMSync Maintenance Assistant, một chatbot AI hỗ trợ nhân viên kỹ thuật trong hệ thống BMSync.

                Xin lỗi, tôi không thể truy cập dữ liệu của bạn lúc này. Tôi sẽ cố gắng trả lời câu hỏi của bạn dựa trên kiến thức chung về bảo trì và kỹ thuật.

                Hãy trả lời câu hỏi sau của Nhân viên kỹ thuật một cách chuyên nghiệp và hữu ích:"""
        else:
            system_prompt = """Bạn là BMSync Assistant, một chatbot AI cho hệ thống quản lý tòa nhà BMSync.

Tôi có thể giúp bạn:
- Tìm hiểu về các dịch vụ của BMSync
- Xem hướng dẫn sử dụng hệ thống
- Gửi yêu cầu hỗ trợ và báo cáo sự cố
- Tra cứu thông tin thiết bị

Hãy trả lời câu hỏi sau một cách thân thiện và hữu ích:"""

        # Prepare request payload
        payload = {
            "contents": [{
                "parts": [{
                    "text": f"{system_prompt}\n\n{message}"
                }]
            }],
            "safetySettings": [{
                "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                "threshold": "BLOCK_ONLY_HIGH"
            }]
        }

        # Make request to Gemini API
        try:
            response = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10  # Add timeout to prevent hanging requests
            )

            if response.status_code != 200:
                logger.error(f"Gemini API error: {response.status_code} - {response.text}")
                return JsonResponse({
                    'response': 'Xin lỗi, tôi đang gặp khó khăn trong việc xử lý yêu cầu của bạn. Vui lòng thử lại sau.',
                    'status': 'error'
                }, status=200)  # Return 200 with error message to display to user

            response_data = response.json()
            generated_text = response_data.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '')

            if not generated_text:
                return JsonResponse({
                    'response': 'Xin lỗi, tôi không thể tạo phản hồi. Vui lòng thử lại với câu hỏi khác.',
                    'status': 'error'
                }, status=200)  # Return 200 with error message to display to user

            return JsonResponse({
                'response': generated_text,
                'status': 'success'
            })
        except requests.exceptions.RequestException as req_error:
            logger.error(f"Request error when calling Gemini API: {str(req_error)}")
            return JsonResponse({
                'response': 'Xin lỗi, có lỗi kết nối khi xử lý yêu cầu của bạn. Vui lòng kiểm tra kết nối mạng và thử lại sau.',
                'status': 'error'
            }, status=200)  # Return 200 with error message to display to user

    except Exception as e:
        logger.error(f"Unexpected error in send_message: {str(e)}", exc_info=True)
        return JsonResponse({
            'response': 'Xin lỗi, đã xảy ra lỗi không mong muốn. Vui lòng thử lại sau.',
            'status': 'error'
        }, status=200)  # Return 200 with error message to display to user