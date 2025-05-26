from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from users.models import UserProfile
from .models import Device, MaintenanceRequest, MaintenanceTask, Report, DeviceRequest
from django.contrib.auth.views import PasswordChangeView
from django.urls import reverse_lazy
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.db.models import Count, F, Func, Value, CharField
from django.utils.timezone import now
from django.views.decorators.http import require_POST, require_http_methods
from django.template.loader import render_to_string
from bmsync.models import Notification, User
from dashboard.models import DeviceRequest, MaintenanceRequest
from django.contrib.auth import update_session_auth_hash
from django.utils import timezone
from django.db.models.functions import ExtractMonth, ExtractYear
import json
import calendar
import logging
import uuid

@login_required
def dashboard_view(request):
    """
    View chính cho dashboard, sẽ render template tương ứng với vai trò của user
    """
    try:
        user_profile = request.user.profile
    except UserProfile.DoesNotExist:
        raise PermissionDenied("User profile not found")
    
    # Lấy template tương ứng với vai trò
    template_name = user_profile.get_dashboard_template()
    
    # Chuẩn bị context dựa trên vai trò
    context = {
        'user_profile': user_profile,
        'role_type': user_profile.role_type,
    }
    
    # Thêm các context đặc biệt cho từng vai trò
    if user_profile.is_maintenance():
        # Lấy tất cả task của user
        maintenance_tasks = MaintenanceTask.objects.filter(assigned_to=user_profile)
        
        # Tính toán số lượng task theo từng trạng thái
        task_counts = maintenance_tasks.values('status').annotate(count=Count('id'))
        task_count_dict = {item['status']: item['count'] for item in task_counts}
        
        # Đếm việc mới: pending + in_progress (progress=0)
        new_tasks_count = maintenance_tasks.filter(status='pending').count() + maintenance_tasks.filter(status='in_progress', progress=0).count()
        context.update({
            'maintenance_tasks': maintenance_tasks,
            'pending_requests': MaintenanceRequest.objects.filter(status='pending'),
            'total_tasks': maintenance_tasks.count(),
            'pending_tasks': new_tasks_count,  # Card 'Việc mới'
            'in_progress_tasks': maintenance_tasks.filter(status='in_progress').exclude(progress=0).count(),
            'completed_tasks': task_count_dict.get('completed', 0),
        })
    elif user_profile.is_manager():
        completed_maintenance = MaintenanceTask.objects.filter(status='completed')
        context.update({
            'total_devices': Device.objects.count(),
            'active_maintenance': MaintenanceTask.objects.filter(status='in_progress'),
            'completed_maintenance': completed_maintenance,
            'completed_maintenance_count': completed_maintenance.count(),
            'reports': Report.objects.all().order_by('-created_at')[:5],
            'critical_issues': MaintenanceRequest.objects.filter(priority='high', status='pending').count(),
        })
    elif user_profile.is_tenant():
        my_devices = Device.objects.filter(tenant=user_profile)
        maintenance_requests = MaintenanceRequest.objects.filter(requester=user_profile)
        completed_requests = MaintenanceTask.objects.filter(maintenance_request__requester=user_profile, status='completed').count()
        # Tính phần trăm (giả sử tối đa 10 cho mỗi loại)
        def percent(val, maxval=10):
            try:
                val = int(val)
                return min(int(val * 100 / maxval), 100)
            except:
                return 0
        context.update({
            'my_devices': my_devices,
            'maintenance_requests': maintenance_requests,
            'maintenance_history': MaintenanceTask.objects.filter(maintenance_request__requester=user_profile, status='completed'),
            'completed_requests': completed_requests,
            'percent_devices': percent(my_devices.count()),
            'percent_requests': percent(maintenance_requests.count()),
            'percent_completed': percent(completed_requests),
        })
    
    return render(request, template_name, context)

@login_required
def notifications_view(request):
    user_profile = request.user.profile
    if request.GET.get('count_only') == '1':
        unread_count = Notification.objects.filter(recipient=request.user, is_read=False).count()
        return JsonResponse({'unread_count': unread_count})
    notifications = Notification.objects.filter(recipient=request.user).order_by('-timestamp')
    # Chọn template theo vai trò
    if user_profile.is_manager():
        template = 'dashboard/notifications_manager.html'
    elif user_profile.is_maintenance():
        template = 'dashboard/notifications_maintenance.html'
    else:
        template = 'dashboard/notifications.html'
    return render(request, template, {
        'notifications': notifications,
        'user_profile': user_profile,
    })

@login_required
def account_settings_view(request):
    """
    View cho phần cài đặt tài khoản
    """
    user_profile = request.user.profile
    
    return render(request, 'dashboard/account_settings.html', {
        'user_profile': user_profile,
    })

@login_required
def tenant_devices_view(request):
    user_profile = request.user.profile
    my_devices = user_profile.devices.all()
    if request.GET.get('ajax') == '1':
        # Trả về JSON danh sách thiết bị
        return JsonResponse({
            'devices': [
                {
                    'id': d.id,
                    'name': d.name,
                    'status': d.status,
                    'status_display': d.get_status_display() if hasattr(d, 'get_status_display') else d.status
                } for d in my_devices
            ]
        })
    return render(request, 'dashboard/tenant_devices.html', {'my_devices': my_devices})

@login_required
def tenant_requests_view(request):
    user_profile = request.user.profile
    maintenance_requests = user_profile.maintenance_requests.all()
    return render(request, 'dashboard/tenant_requests.html', {'maintenance_requests': maintenance_requests})

@login_required
def tenant_history_view(request):
    user_profile = request.user.profile
    maintenance_history = MaintenanceTask.objects.filter(maintenance_request__requester=user_profile, status='completed')
    return render(request, 'dashboard/tenant_history.html', {'maintenance_history': maintenance_history})

@login_required
def tenant_account_view(request):
    user_profile = request.user.profile
    return render(request, 'dashboard/tenant_account.html', {'user_profile': user_profile})

class TenantPasswordChangeView(PasswordChangeView):
    template_name = 'dashboard/tenant_change_password.html'
    success_url = reverse_lazy('dashboard:tenant_account')

@login_required
@csrf_exempt
def tenant_add_device_request(request):
    if request.method == 'POST':
        name = request.POST.get('device_name')
        type_ = request.POST.get('device_type')
        location = request.POST.get('device_location')
        note = request.POST.get('device_note')
        req = DeviceRequest.objects.create(
            name=name,
            type=type_,
            location=location,
            note=note,
            requester=request.user.profile,
            status='pending',
        )
        # Gửi thông báo cho tất cả Manager
        managers = UserProfile.objects.filter(role_type='manager')
        for m in managers:
            Notification.objects.create(
                recipient=m.user,
                message=f"Yêu cầu thêm thiết bị '{name}' từ {request.user.username}.",
                notification_type='new_request',
                related_object_id=req.id
            )
        return JsonResponse({'success': True})
    return JsonResponse({'success': False}, status=400)

@login_required
@csrf_exempt
def tenant_contact_manager(request):
    if request.method == 'POST':
        subject = request.POST.get('contact_subject')
        message = request.POST.get('contact_message')
        # Gửi thông báo cho tất cả manager
        managers = UserProfile.objects.filter(role_type='manager')
        for m in managers:
            Notification.objects.create(
                recipient=m.user,
                message=f"Liên hệ quản trị: {subject} - {message}",
                notification_type='other',
                related_object_id=request.user.id
            )
        return JsonResponse({'success': True})
    return JsonResponse({'success': False}, status=400)

@login_required
def tenant_add_device_view(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        type_ = request.POST.get('device_type')
        location = request.POST.get('location')
        status = request.POST.get('status', 'active')
        
        # Generate a unique device_id
        device_id = f"DEV-{uuid.uuid4().hex[:8].upper()}"
        
        Device.objects.create(
            device_id=device_id,
            name=name,
            device_type=type_,
            location=location,
            status=status,
            tenant=request.user.profile
        )
        messages.success(request, 'Đã thêm thiết bị thành công!')
        return redirect('dashboard:tenant_devices')
    return render(request, 'dashboard/tenant_add_device.html', {})

@login_required
@csrf_exempt
def tenant_delete_device(request):
    if request.method == 'POST':
        device_id = request.POST.get('device_id')
        device = Device.objects.filter(id=device_id, tenant=request.user.profile).first()
        if device:
            device.delete()
            return JsonResponse({'success': True})
    return JsonResponse({'success': False}, status=400)

@login_required
@csrf_exempt
def tenant_edit_device(request):
    if request.method == 'POST':
        device_id = request.POST.get('device_id')
        device = Device.objects.filter(id=device_id, tenant=request.user.profile).first()
        if device:
            device.name = request.POST.get('device_name')
            device.device_type = request.POST.get('device_type')
            device.location = request.POST.get('device_location')
            device.status = request.POST.get('device_status')
            device.save()
            return JsonResponse({'success': True})
    return JsonResponse({'success': False}, status=400)

@login_required
@csrf_exempt
def tenant_request_maintenance(request):
    if request.method == 'POST':
        device_id = request.POST.get('device_id')
        title = request.POST.get('title')
        description = request.POST.get('description')
        device = Device.objects.filter(id=device_id, tenant=request.user.profile).first()
        if device:
            maintenance_req = MaintenanceRequest.objects.create(
                requester=request.user.profile,
                device=device,
                title=title,
                description=description,
                status='pending', 
                priority='medium' 
            )
            # Thông báo cho Managers
            managers = UserProfile.objects.filter(role_type='manager')
            for manager_profile in managers:
                Notification.objects.create(
                    recipient=manager_profile.user,
                    message=f"Yêu cầu bảo trì mới: '{title}' cho thiết bị '{device.name}'.",
                    notification_type='maintenance_request',
                    related_object_id=maintenance_req.id
                )
            return JsonResponse({'success': True})
    return JsonResponse({'success': False}, status=400)

@login_required
@require_POST
def rate_task_view(request):
    try:
        task_id = request.POST.get('task_id')
        rating_value = request.POST.get('rating')
        rating_comment = request.POST.get('rating_comment', '') # Optional

        if not task_id or not rating_value:
            return JsonResponse({'success': False, 'message': 'Thiếu thông tin ID công việc hoặc đánh giá.'}, status=400)

        try:
            rating_value = int(rating_value)
            if not (1 <= rating_value <= 5):
                raise ValueError("Rating out of range")
        except ValueError:
            return JsonResponse({'success': False, 'message': 'Đánh giá không hợp lệ.'}, status=400)

        task = get_object_or_404(MaintenanceTask, id=task_id)

        # Check if the user is the one who requested the maintenance for this task
        if task.maintenance_request.requester != request.user.profile:
            return JsonResponse({'success': False, 'message': 'Bạn không có quyền đánh giá công việc này.'}, status=403)

        if task.rating is not None:
            return JsonResponse({'success': False, 'message': 'Công việc này đã được đánh giá trước đó.'}, status=400)
        
        if task.status != 'completed':
            return JsonResponse({'success': False, 'message': 'Chỉ có thể đánh giá công việc đã hoàn thành.'}, status=400)


        task.rating = rating_value
        task.rating_comment = rating_comment
        task.rated_at = timezone.now()
        task.save()

        return JsonResponse({'success': True, 'message': 'Đánh giá đã được lưu thành công.'})

    except MaintenanceTask.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Không tìm thấy công việc.'}, status=404)
    except Exception as e:
        # Log the error e for debugging
        print(f"Error in rate_task_view: {e}")
        return JsonResponse({'success': False, 'message': 'Có lỗi xảy ra phía máy chủ.'}, status=500)

@login_required
@csrf_exempt
def tenant_update_info(request):
    if request.method == 'POST':
        fullname = request.POST.get('fullname')
        email = request.POST.get('email')
        user = request.user
        if fullname:
            parts = fullname.strip().split(' ', 1)
            user.first_name = parts[0]
            user.last_name = parts[1] if len(parts) > 1 else ''
        if email:
            user.email = email
        user.save()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False}, status=400)

@login_required
def tenant_device_detail_view(request, device_id):
    user_profile = request.user.profile
    device = Device.objects.filter(id=device_id, tenant=user_profile).first()
    if not device:
        return redirect('dashboard:tenant_devices')
    return render(request, 'dashboard/tenant_device_detail.html', {'device': device})

@login_required
def tenant_device_edit_view(request, device_id):
    user_profile = request.user.profile
    device = Device.objects.filter(id=device_id, tenant=user_profile).first()
    if not device:
        return redirect('dashboard:tenant_devices')
    if request.method == 'POST':
        device.name = request.POST.get('name')
        device.device_type = request.POST.get('device_type')
        device.location = request.POST.get('location')
        device.status = request.POST.get('status')
        device.save()
        messages.success(request, 'Đã cập nhật thiết bị thành công!')
        return redirect('dashboard:tenant_device_detail', device_id=device.id)
    return render(request, 'dashboard/tenant_device_edit.html', {'device': device})

@login_required
def tenant_request_detail_view(request, request_id):
    user_profile = request.user.profile
    req = MaintenanceRequest.objects.filter(id=request_id, requester=user_profile).first()
    if not req:
        return redirect('dashboard:tenant_requests')
    device = req.device
    return render(request, 'dashboard/tenant_request_detail.html', {'req': req, 'device': device})

@login_required
def manager_devices_view(request):
    devices = Device.objects.all()
    return render(request, 'dashboard/manager_devices.html', {'devices': devices})

@login_required
def manager_device_detail_view(request, device_id):
    device = Device.objects.filter(id=device_id).first()
    if not device:
        messages.error(request, 'Không tìm thấy thiết bị!')
        return redirect('dashboard:manager_devices')
    return render(request, 'dashboard/manager_device_detail.html', {'device': device})

@login_required
def manager_device_edit_view(request, device_id):
    device = Device.objects.filter(id=device_id).first()
    if not device:
        messages.error(request, 'Không tìm thấy thiết bị!')
        return redirect('dashboard:manager_devices')
    
    if request.method == 'POST':
        device.name = request.POST.get('name')
        device.device_type = request.POST.get('device_type')
        device.location = request.POST.get('location')
        device.status = request.POST.get('status')
        device.save()
        messages.success(request, 'Đã cập nhật thiết bị thành công!')
        return redirect('dashboard:manager_device_detail', device_id=device.id)
    
    return render(request, 'dashboard/manager_device_edit.html', {'device': device})

@login_required
@csrf_exempt
def manager_delete_device(request):
    if request.method == 'POST':
        device_id = request.POST.get('device_id')
        device = Device.objects.filter(id=device_id).first()
        if device:
            device.delete()
            return JsonResponse({'success': True})
    return JsonResponse({'success': False}, status=400)

@login_required
def manager_requests_view(request):
    requests = MaintenanceRequest.objects.all().order_by('-created_at')
    return render(request, 'dashboard/manager_requests.html', {'requests': requests})

@login_required
def manager_reports_view(request):
    reports = Report.objects.all().order_by('-created_at')
    return render(request, 'dashboard/manager_reports.html', {'reports': reports})

@login_required
def manager_account_view(request):
    user_profile = request.user.profile
    return render(request, 'dashboard/manager_account.html', {'user_profile': user_profile})

@login_required
def manager_request_detail_view(request, request_id):
    req = MaintenanceRequest.objects.filter(id=request_id).first()
    maintenances = UserProfile.objects.filter(role_type='maintenance')
    if not req:
        return redirect('dashboard:manager_requests')
    if request.method == 'POST':
        if req.status != 'pending':
            messages.error(request, 'Yêu cầu này đã được giao, không thể giao lại!')
            return render(request, 'dashboard/manager_request_detail.html', {'req': req, 'maintenances': maintenances})
        assign_to_id = request.POST.get('assign_to')
        if assign_to_id:
            assignee = UserProfile.objects.filter(id=assign_to_id).first()
            if assignee:
                req.assigned_to = assignee
                req.status = 'assigned'
                req.save()
                # KHÔNG tạo MaintenanceTask ở đây nữa
                Notification.objects.create(
                    recipient=assignee.user,
                    message=f"Bạn vừa được giao yêu cầu bảo trì: {req.title}",
                    notification_type='task_assigned',
                    related_object_id=req.id
                )
                assignee_name = assignee.user.get_full_name() or assignee.user.username
                Notification.objects.create(
                    recipient=request.user,
                    message=f"Đã giao việc '{req.title}' cho {assignee_name}",
                    notification_type='request_processed',
                    related_object_id=req.id
                )
                # Gửi thông báo cho Tenant (requester)
                Notification.objects.create(
                    recipient=req.requester.user,
                    message=f"Yêu cầu bảo trì của bạn đã được xác nhận và đang chờ xử lý.",
                    notification_type='request_processed',
                    related_object_id=req.id
                )
                messages.success(request, 'Giao việc thành công!')
                return redirect('dashboard:manager_request_detail', request_id=req.id)
            else:
                messages.error(request, 'Không tìm thấy nhân viên bảo trì.')
        else:
            messages.error(request, 'Vui lòng chọn nhân viên bảo trì.')
    return render(request, 'dashboard/manager_request_detail.html', {'req': req, 'maintenances': maintenances})

class ManagerPasswordChangeView(PasswordChangeView):
    template_name = 'dashboard/manager_change_password.html'
    success_url = reverse_lazy('dashboard:manager_account')

@login_required
def manager_update_info(request):
    user_profile = request.user.profile
    if request.method == 'POST':
        fullname = request.POST.get('fullname')
        email = request.POST.get('email')
        user = request.user
        if fullname:
            parts = fullname.strip().split(' ', 1)
            user.first_name = parts[0]
            user.last_name = parts[1] if len(parts) > 1 else ''
        if email:
            user.email = email
        user.save()
        return JsonResponse({'success': True})
    # Nếu là GET thì trả về form cập nhật thông tin
    return render(request, 'dashboard/manager_update_info.html', {'user_profile': user_profile})

@login_required
@csrf_exempt
def manager_chart_data_api(request):
    if request.method == 'POST':
        chart_type = request.POST.get('chartType')
        data_source = request.POST.get('dataSource')
        group_by = request.POST.get('groupBy')
        selected_year_str = request.POST.get('selectedYear')

        labels = []
        data = []
        label = ''
        
        # Prepare month map for i18n or custom naming if needed
        month_map = {i: f'Tháng {i}' for i in range(1, 13)}

        if data_source == 'device':
            qs = Device.objects.all()
            if group_by == 'month':
                selected_year = None
                if selected_year_str and selected_year_str.isdigit():
                    selected_year = int(selected_year_str)

                query = qs
                if selected_year:
                    query = query.filter(last_updated__year=selected_year)
                
                result = (
                    query.annotate(month=ExtractMonth('last_updated'))
                    .values('month')
                    .annotate(count=Count('id'))
                    .order_by('month')
                )
                month_count = {r['month']: r['count'] for r in result}
                labels = [month_map.get(i, f'Tháng {i}') for i in range(1, 13)]
                data = [month_count.get(i, 0) for i in range(1, 13)]
                year_label = f"năm {selected_year}" if selected_year else "tất cả các năm"
                label = f'Số lượng thiết bị (cập nhật) theo tháng ({year_label})'

            elif group_by == 'year':
                result = (
                    qs.annotate(year=ExtractYear('last_updated'))
                    .values('year')
                    .annotate(count=Count('id'))
                    .order_by('year')
                )
                labels = [r['year'] for r in result if r['year'] is not None]
                data = [r['count'] for r in result if r['year'] is not None]
                label = 'Số lượng thiết bị (cập nhật) theo năm'
            elif group_by == 'status':
                result = qs.values('status').annotate(count=Count('id')).order_by('status')
                status_map = dict(Device._meta.get_field('status').choices)
                labels = [status_map.get(r['status'], r['status']) for r in result]
                data = [r['count'] for r in result]
                label = 'Số lượng thiết bị theo trạng thái'
            elif group_by == 'type':
                result = qs.values('device_type').annotate(count=Count('id')).order_by('device_type')
                type_map = dict(Device._meta.get_field('device_type').choices)
                labels = [type_map.get(r['device_type'], r['device_type']) for r in result]
                data = [r['count'] for r in result]
                label = 'Số lượng thiết bị theo loại'
        elif data_source == 'request':
            qs = MaintenanceRequest.objects.all()
            if group_by == 'month':
                selected_year = None
                if selected_year_str and selected_year_str.isdigit():
                    selected_year = int(selected_year_str)

                query = qs
                if selected_year:
                    query = query.filter(created_at__year=selected_year)

                result = (
                    query.annotate(month=ExtractMonth('created_at'))
                    .values('month')
                    .annotate(count=Count('id'))
                    .order_by('month')
                )
                month_count = {r['month']: r['count'] for r in result}
                labels = [month_map.get(i, f'Tháng {i}') for i in range(1, 13)]
                data = [month_count.get(i, 0) for i in range(1, 13)]
                year_label = f"năm {selected_year}" if selected_year else "tất cả các năm"
                label = f'Số lượng yêu cầu bảo trì theo tháng ({year_label})'

            elif group_by == 'year':
                result = (
                    qs.annotate(year=ExtractYear('created_at'))
                    .values('year')
                    .annotate(count=Count('id'))
                    .order_by('year')
                )
                labels = [r['year'] for r in result if r['year'] is not None]
                data = [r['count'] for r in result if r['year'] is not None]
                label = 'Số lượng yêu cầu bảo trì theo năm'
            elif group_by == 'status':
                result = qs.values('status').annotate(count=Count('id')).order_by('status')
                status_map = dict(MaintenanceRequest._meta.get_field('status').choices)
                labels = [status_map.get(r['status'], r['status']) for r in result]
                data = [r['count'] for r in result]
                label = 'Yêu cầu bảo trì theo trạng thái'
            elif group_by == 'priority':
                result = qs.values('priority').annotate(count=Count('id')).order_by('priority')
                priority_map = dict(MaintenanceRequest._meta.get_field('priority').choices)
                labels = [priority_map.get(r['priority'], r['priority']) for r in result]
                data = [r['count'] for r in result]
                label = 'Yêu cầu bảo trì theo mức ưu tiên'
        elif data_source == 'user':
            qs = UserProfile.objects.all()
            if group_by == 'role':
                result = qs.values('role_type').annotate(count=Count('id')).order_by('role_type')
                role_map = {'tenant': 'Tenant', 'manager': 'Manager', 'maintenance': 'Maintenance'}
                labels = [role_map.get(r['role_type'], r['role_type']) for r in result]
                data = [r['count'] for r in result]
                label = 'Số lượng người dùng theo vai trò'
            elif group_by == 'month':
                selected_year = None
                if selected_year_str and selected_year_str.isdigit():
                    selected_year = int(selected_year_str)

                query = qs
                if selected_year:
                    query = query.filter(user__date_joined__year=selected_year)
                
                result = (
                    query.annotate(month=ExtractMonth('user__date_joined'))
                    .values('month')
                    .annotate(count=Count('id'))
                    .order_by('month')
                )
                month_count = {r['month']: r['count'] for r in result}
                labels = [month_map.get(i, f'Tháng {i}') for i in range(1, 13)]
                data = [month_count.get(i, 0) for i in range(1, 13)]
                year_label = f"năm {selected_year}" if selected_year else "tất cả các năm"
                label = f'Số lượng người dùng mới theo tháng ({year_label})'
            elif group_by == 'year':
                result = (
                    qs.annotate(year=ExtractYear('user__date_joined'))
                    .values('year')
                    .annotate(count=Count('id'))
                    .order_by('year')
                )
                labels = [r['year'] for r in result if r['year'] is not None]
                data = [r['count'] for r in result if r['year'] is not None]
                label = 'Số lượng người dùng mới theo năm'

        return JsonResponse({'labels': labels, 'data': data, 'label': label})
    return JsonResponse({'error': 'Invalid request'}, status=400)

@login_required
@require_POST
def manager_save_chart(request):
    name = request.POST.get('name')
    chart_type = request.POST.get('chartType')
    labels = request.POST.get('labels')
    data = request.POST.get('data')
    label = request.POST.get('label')
    report_type = request.POST.get('reportType', 'device')  # Mặc định là 'device'
    user_profile = request.user.profile
    # Lưu vào model Report (hoặc Chart nếu có)
    description = json.dumps({
        'labels': json.loads(labels) if labels else [],
        'data': json.loads(data) if data else [],
        'label': label or 'Biểu đồ',
        'chartType': chart_type,
    })
    Report.objects.create(
        title=name,
        description=description,
        type=report_type,
        author=user_profile,
    )
    return JsonResponse({'success': True})

@login_required
def manager_list_charts(request):
    user_profile = request.user.profile
    charts = Report.objects.filter(author=user_profile).order_by('-created_at')
    html = render_to_string('dashboard/manager_saved_charts_table.html', {'charts': charts})
    return HttpResponse(html)

@login_required
def manager_device_requests_view(request):
    user_profile = request.user.profile
    if not user_profile.is_manager():
        raise PermissionDenied("Chỉ Manager mới được truy cập.")
    requests = DeviceRequest.objects.filter(status='pending').order_by('-created_at')
    return render(request, 'dashboard/manager_device_requests.html', {'requests': requests})

@login_required
@require_POST
def manager_approve_device_request(request):
    req_id = request.POST.get('request_id')
    action = request.POST.get('action')  # 'approve' hoặc 'reject'
    req = DeviceRequest.objects.filter(id=req_id, status='pending').first()
    if not req:
        return JsonResponse({'success': False, 'error': 'Yêu cầu không tồn tại hoặc đã xử lý.'})
    if action == 'approve':
        req.status = 'approved'
        req.save()
        # Tạo thiết bị mới
        Device.objects.create(
            name=req.name,
            type=req.type,
            location=req.location,
            tenant=req.requester,
            status='active',
        )
        # Gửi thông báo cho Tenant
        Notification.objects.create(
            recipient=req.requester.user,
            message=f"Yêu cầu thêm thiết bị '{req.name}' đã được phê duyệt và thiết bị đã được thêm vào hệ thống.",
            notification_type='request_processed',
            related_object_id=req.id
        )
        return JsonResponse({'success': True, 'msg': 'Đã phê duyệt và thêm thiết bị.'})
    elif action == 'reject':
        req.status = 'rejected'
        req.save()
        Notification.objects.create(
            recipient=req.requester.user,
            message=f"Yêu cầu thêm thiết bị '{req.name}' đã bị từ chối.",
            notification_type='request_processed',
            related_object_id=req.id
        )
        return JsonResponse({'success': True, 'msg': 'Đã từ chối yêu cầu.'})
    return JsonResponse({'success': False, 'error': 'Hành động không hợp lệ.'})

@login_required
def manager_chart_detail_view(request, chart_id):
    user_profile = request.user.profile
    chart = get_object_or_404(Report, id=chart_id, author=user_profile)
    labels = []
    data = []
    label = chart.description or 'Biểu đồ'
    chart_type = 'bar'
    # Nếu có lưu labels/data trong description dạng JSON thì parse ra
    try:
        desc = json.loads(chart.description)
        labels = desc.get('labels', [])
        data = desc.get('data', [])
        label = desc.get('label', label)
        chart_type = desc.get('chartType', 'bar')
    except Exception as e:
        logging.error(f"Lỗi parse description JSON: {e}, raw: {chart.description}")
        labels = []
        data = []
        label = chart.description
        chart_type = 'bar'
    context = {
        'chart': chart,
        'labels': labels,
        'data': data,
        'type': chart_type,  # Đúng kiểu cho Chart.js
        'label': label,
        'raw_description': chart.description, # debug
    }
    return render(request, 'dashboard/manager_chart_detail.html', context)

@login_required
@require_http_methods(["GET", "POST"])
def notification_detail_view(request, notification_id):
    notification = get_object_or_404(Notification, id=notification_id, recipient=request.user)
    user_profile = request.user.profile
    # Đánh dấu đã đọc nếu chưa
    if not notification.is_read:
        notification.is_read = True
        notification.save()
    # GET: trả về chi tiết thông báo (dùng cho modal)
    if request.method == "GET":
        context = {"notification": notification, "user_profile": user_profile}
        # Nếu là yêu cầu thêm thiết bị
        if notification.notification_type == "new_request" and notification.message.startswith("Yêu cầu thêm thiết bị"):
            # Lấy DeviceRequest liên quan
            device_req = DeviceRequest.objects.filter(id=notification.related_object_id).first()
            context["device_req"] = device_req
            return render(request, "dashboard/notification_detail_device_request.html", context)
        # Nếu là yêu cầu bảo trì
        if notification.notification_type == "maintenance_request":
            maintenance_request = MaintenanceRequest.objects.filter(id=notification.related_object_id).first()
            maintenances = UserProfile.objects.filter(role_type='maintenance')
            context["maintenance_request"] = maintenance_request
            context["maintenances"] = maintenances
            return render(request, "dashboard/notification_detail_maintenance_request.html", context)
        # Nếu là liên hệ quản trị
        elif notification.notification_type == "other" and notification.message.startswith("Liên hệ quản trị"):
            # Có thể lấy thêm dữ liệu nếu cần
            return render(request, "dashboard/notification_detail_contact.html", context)
        # Nếu là phản hồi cho tenant
        elif notification.notification_type == "request_processed" and user_profile.is_tenant():
            # Hiển thị form cho tenant điền chi tiết hơn
            return render(request, "dashboard/notification_detail_tenant_response.html", context)
        # Nếu là task_assigned cho maintenance, truyền thêm trạng thái task
        if notification.notification_type == "task_assigned" and user_profile.is_maintenance():
            req = MaintenanceRequest.objects.filter(id=notification.related_object_id).first()
            task = None
            if req:
                task = MaintenanceTask.objects.filter(maintenance_request=req, assigned_to=user_profile).first()
            context["task_status"] = task.status if task else None
        # Mặc định: chỉ hiển thị nội dung
        if user_profile.is_manager():
            return render(request, "dashboard/notification_detail_manager.html", context)
        return render(request, "dashboard/notification_detail.html", context)
    # POST: xử lý thao tác
    action = request.POST.get("action")
    if not action:
        return JsonResponse({"success": False, "msg": "Không có thao tác nào được thực hiện."})
    # Phê duyệt yêu cầu thêm thiết bị
    if action == "approve_device_request" and user_profile.is_manager():
        device_req = DeviceRequest.objects.filter(id=notification.related_object_id).first()
        if device_req and device_req.status == "pending":
            device_req.status = "approved"
            device_req.save()
            # Tạo thiết bị mới
            Device.objects.create(
                name=device_req.name,
                type=device_req.type,
                location=device_req.location,
                tenant=device_req.requester,
                status="active",
            )
            # Gửi thông báo cho tenant
            Notification.objects.create(
                recipient=device_req.requester.user,
                message=f"Yêu cầu thêm thiết bị '{device_req.name}' đã được phê duyệt và thiết bị đã được thêm vào hệ thống.",
                notification_type="request_processed",
                related_object_id=device_req.id
            )
            return JsonResponse({"success": True, "msg": "Đã phê duyệt và thêm thiết bị."})
        return JsonResponse({"success": False, "msg": "Yêu cầu không hợp lệ hoặc đã xử lý."})
    # Từ chối yêu cầu thêm thiết bị
    if action == "reject_device_request" and user_profile.is_manager():
        device_req = DeviceRequest.objects.filter(id=notification.related_object_id).first()
        if device_req and device_req.status == "pending":
            device_req.status = "rejected"
            device_req.save()
            Notification.objects.create(
                recipient=device_req.requester.user,
                message=f"Yêu cầu thêm thiết bị '{device_req.name}' đã bị từ chối.",
                notification_type="request_processed",
                related_object_id=device_req.id
            )
            return JsonResponse({"success": True, "msg": "Đã từ chối yêu cầu."})
        return JsonResponse({"success": False, "msg": "Yêu cầu không hợp lệ hoặc đã xử lý."})
    # Phản hồi liên hệ quản trị
    if action == "reply_contact" and user_profile.is_manager():
        reply_message = request.POST.get("reply_message")
        tenant_id = request.POST.get("tenant_id")
        tenant_user = User.objects.filter(id=tenant_id).first()
        if tenant_user:
            Notification.objects.create(
                recipient=tenant_user,
                message=f"Phản hồi từ quản trị viên: {reply_message}",
                notification_type="request_processed",
                related_object_id=notification.id
            )
            return JsonResponse({"success": True, "msg": "Đã gửi phản hồi cho tenant."})
        return JsonResponse({"success": False, "msg": "Không tìm thấy tenant."})
    # Tenant gửi lại form chi tiết
    if action == "tenant_response" and user_profile.is_tenant():
        detail = request.POST.get("detail")
        request_type = request.POST.get("request_type")
        # Gửi thông báo cho manager
        managers = UserProfile.objects.filter(role_type="manager")
        for m in managers:
            Notification.objects.create(
                recipient=m.user,
                message=f"Tenant {request.user.username} đã phản hồi: {detail} (Loại: {request_type})",
                notification_type="new_request",
                related_object_id=notification.id
            )
        return JsonResponse({"success": True, "msg": "Đã gửi phản hồi cho quản trị viên."})
    # Duyệt yêu cầu bảo trì
    if action == "approve_maintenance_request" and user_profile.is_manager():
        maintenance_request = MaintenanceRequest.objects.filter(id=notification.related_object_id).first()
        if maintenance_request and maintenance_request.status == "pending":
            maintenance_request.status = "approved"
            maintenance_request.save()
            # Gửi thông báo cho Tenant
            Notification.objects.create(
                recipient=maintenance_request.requester.user,
                message=f"Yêu cầu bảo trì '{maintenance_request.title}' của bạn đã được duyệt và đang chờ giao việc.",
                notification_type="request_processed",
                related_object_id=maintenance_request.id
            )
            return JsonResponse({"success": True, "msg": "Đã duyệt yêu cầu. Bạn có thể giao việc cho nhân viên bảo trì."})
        return JsonResponse({"success": False, "msg": "Yêu cầu không hợp lệ hoặc đã xử lý."})
    # Giao việc cho Maintenance
    if action == "assign_maintenance" and user_profile.is_manager():
        maintenance_request = MaintenanceRequest.objects.filter(id=notification.related_object_id).first()
        assign_to_id = request.POST.get('assign_to')
        assignee = UserProfile.objects.filter(id=assign_to_id, role_type='maintenance').first()
        if maintenance_request and maintenance_request.status == "approved" and assignee:
            maintenance_request.assigned_to = assignee
            maintenance_request.status = "assigned"
            maintenance_request.save()
            # Tạo MaintenanceTask nếu chưa có
            task = MaintenanceTask.objects.filter(maintenance_request=maintenance_request, assigned_to=assignee).first()
            if not task:
                MaintenanceTask.objects.create(
                    maintenance_request=maintenance_request,
                    assigned_to=assignee,
                    title=maintenance_request.title,
                    description=maintenance_request.description,
                    due_date=timezone.now() + timezone.timedelta(days=3),
                    status='pending',
                )
            # Gửi thông báo cho Maintenance
            Notification.objects.create(
                recipient=assignee.user,
                message=f"Bạn vừa được giao yêu cầu bảo trì: {maintenance_request.title}",
                notification_type="task_assigned",
                related_object_id=maintenance_request.id
            )
            # Gửi thông báo cho Tenant
            Notification.objects.create(
                recipient=maintenance_request.requester.user,
                message=f"Yêu cầu bảo trì '{maintenance_request.title}' của bạn đã được giao cho {assignee.user.get_full_name() or assignee.user.username}.",
                notification_type="request_processed",
                related_object_id=maintenance_request.id
            )
            return JsonResponse({"success": True, "msg": "Đã giao việc cho nhân viên bảo trì."})
        return JsonResponse({"success": False, "msg": "Yêu cầu không hợp lệ hoặc đã xử lý."})
    # Xác nhận nhận việc cho Maintenance (kỹ thuật viên)
    if action == "accept_task" and user_profile.is_maintenance():
        req = MaintenanceRequest.objects.filter(id=notification.related_object_id).first()
        if not req:
            return JsonResponse({"success": False, "msg": "Không tìm thấy yêu cầu bảo trì."})
        # Tìm task đã gán cho kỹ thuật viên này với request này
        task = MaintenanceTask.objects.filter(maintenance_request=req, assigned_to=user_profile).first()
        if not task:
            # Nếu chưa có task, tạo mới
            task = MaintenanceTask.objects.create(
                maintenance_request=req,
                assigned_to=user_profile,
                title=req.title,
                description=req.description,
                due_date=timezone.now() + timezone.timedelta(days=3),
                status='in_progress',
            )
            req.status = 'assigned'
            req.save()
            return JsonResponse({"success": True, "msg": "Đã nhận việc và tạo công việc bảo trì!"})
        else:
            if task.status == 'pending':
                task.status = 'in_progress'
                task.save()
                req.status = 'assigned'
                req.save()
                return JsonResponse({"success": True, "msg": "Đã xác nhận nhận việc!"})
            elif task.status == 'in_progress':
                return JsonResponse({"success": False, "msg": "Bạn đã nhận việc này rồi!"})
            elif task.status == 'completed':
                return JsonResponse({"success": False, "msg": "Công việc này đã hoàn thành!"})
            else:
                return JsonResponse({"success": False, "msg": "Không thể nhận việc này."})
    return JsonResponse({"success": False, "msg": "Hành động không hợp lệ."}, status=400)

@login_required
def maintenance_tasks_view(request):
    user_profile = request.user.profile
    if not user_profile.is_maintenance():
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("Chỉ nhân viên kỹ thuật mới được truy cập.")
    maintenance_tasks = user_profile.maintenance_tasks.all()
    context = {
        'maintenance_tasks': maintenance_tasks,
        'user_profile': user_profile,
    }
    return render(request, 'dashboard/maintenance_tasks.html', context)

@login_required
def maintenance_history_view(request):
    user_profile = request.user.profile
    if not user_profile.is_maintenance():
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("Chỉ nhân viên kỹ thuật mới được truy cập.")
    history_tasks = user_profile.maintenance_tasks.filter(status='completed')
    context = {
        'history_tasks': history_tasks,
        'user_profile': user_profile,
    }
    return render(request, 'dashboard/maintenance_history.html', context)

@login_required
def maintenance_account_view(request):
    user_profile = request.user.profile
    if not user_profile.is_maintenance():
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("Chỉ nhân viên kỹ thuật mới được truy cập.")
    
    if request.method == 'POST':
        # Xử lý cập nhật thông tin
        full_name = request.POST.get('full_name')
        if full_name:
            parts = full_name.strip().split(' ', 1)
            user_profile.user.first_name = parts[0]
            user_profile.user.last_name = parts[1] if len(parts) > 1 else ''
            user_profile.user.save()
        # Xử lý đổi mật khẩu nếu có
        current_password = request.POST.get('current_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        if current_password and new_password and confirm_password:
            if not request.user.check_password(current_password):
                messages.error(request, 'Mật khẩu hiện tại không đúng')
            elif new_password != confirm_password:
                messages.error(request, 'Mật khẩu mới không khớp')
            else:
                request.user.set_password(new_password)
                request.user.save()
                update_session_auth_hash(request, request.user)
                messages.success(request, 'Mật khẩu đã được cập nhật')
        user_profile.save()
        messages.success(request, 'Thông tin tài khoản đã được cập nhật')
        return redirect('dashboard:maintenance_account')
    
    context = {
        'user_profile': user_profile,
    }
    return render(request, 'dashboard/maintenance_account.html', context)

@login_required
def maintenance_task_detail_view(request, task_id):
    user_profile = request.user.profile
    task = get_object_or_404(MaintenanceTask, id=task_id, assigned_to=user_profile)
    return render(request, 'dashboard/maintenance_task_detail.html', {'task': task, 'user_profile': user_profile})

@login_required
@require_POST
def start_task_view(request, task_id):
    user_profile = request.user.profile
    task = get_object_or_404(MaintenanceTask, id=task_id, assigned_to=user_profile)
    if task.status == 'pending':
        task.status = 'in_progress'
        task.save()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'msg': 'Không thể bắt đầu xử lý task này.'})

@login_required
@require_POST
def complete_task_view(request, task_id):
    user_profile = request.user.profile
    task = get_object_or_404(MaintenanceTask, id=task_id, assigned_to=user_profile)
    if task.status == 'in_progress':
        task.status = 'completed'
        task.progress = 100  # Đảm bảo tiến độ là 100%
        task.save()
        # Gửi thông báo cho Tenant (requester của MaintenanceRequest)
        if task.maintenance_request and task.maintenance_request.requester:
            Notification.objects.create(
                recipient=task.maintenance_request.requester.user,
                message=f"Yêu cầu bảo trì '{task.title}' của bạn đã được hoàn thành.",
                notification_type='request_processed',
                related_object_id=task.maintenance_request.id
            )
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'msg': 'Không thể hoàn thành task này.'})

@login_required
def manager_create_chart_view(request):
    user_profile = request.user.profile
    devices = Device.objects.filter(created_by=user_profile)
    # Lấy dữ liệu từ cột "Ngày cập nhật" của thiết bị
    device_data = []
    for device in devices:
        device_data.append({
            'name': device.name,
            'updated_at': device.updated_at,
        })
    # Xử lý lại để tạo biểu đồ cột với nguồn dữ liệu "Thiết bị" và "thống kê theo:" tháng
    months = list(calendar.month_name)[1:]
    device_count_by_month = [0] * 12
    for device in device_data:
        month = device['updated_at'].month - 1
        device_count_by_month[month] += 1
    context = {
        'devices': devices,
        'months': months,
        'device_count_by_month': device_count_by_month,
    }
    return render(request, 'dashboard/manager_create_chart.html', context)

@login_required
@require_POST
def manager_delete_chart(request, chart_id):
    user_profile = request.user.profile
    try:
        chart = Report.objects.get(id=chart_id, author=user_profile)
        chart.delete()
        return JsonResponse({'success': True})
    except Report.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Không tìm thấy biểu đồ.'}, status=404)

@login_required
@require_POST
def update_task_progress(request, task_id):
    user_profile = request.user.profile
    task = get_object_or_404(MaintenanceTask, id=task_id, assigned_to=user_profile)
    try:
        progress = int(request.POST.get('progress', 0))
        if progress < 0: progress = 0
        if progress > 100: progress = 100
        task.progress = progress
        task.save(update_fields=['progress'])
        return JsonResponse({'success': True, 'progress': task.progress})
    except Exception as e:
        return JsonResponse({'success': False, 'msg': f'Lỗi: {e}'})

@login_required
def manager_dashboard(request):
    # Get all devices (since we don't have manager-specific filtering yet)
    devices = Device.objects.all()
    
    # Calculate statistics based on device status
    total_devices = devices.count()
    active_devices = devices.filter(status='active').count()
    maintenance_devices = devices.filter(status='maintenance').count()
    critical_issues = devices.filter(status__in=['broken', 'inactive']).count()
    
    # Get maintenance tasks
    maintenance_tasks = MaintenanceTask.objects.all()
    active_maintenance = maintenance_tasks.filter(status__in=['pending', 'in_progress'])
    completed_maintenance = maintenance_tasks.filter(status='completed')
    
    # Get recent reports
    reports = Report.objects.all().order_by('-created_at')[:10]
    
    context = {
        'total_devices': total_devices,
        'active_devices': active_devices,
        'maintenance_devices': maintenance_devices,
        'critical_issues': critical_issues,
        'active_maintenance': active_maintenance,
        'completed_maintenance': completed_maintenance,
        'completed_maintenance_count': completed_maintenance.count(),
        'reports': reports,
    }
    
    return render(request, 'dashboard/manager_dashboard.html', context) 