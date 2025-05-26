from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from .models import MaintenanceRequest
from .forms import MaintenanceRequestForm
from django.contrib.auth import get_user_model

def maintenance_request_list(request):
    requests = MaintenanceRequest.objects.all().order_by('-created_at')
    return render(request, 'maintenance/maintenance_request_list.html', {'requests': requests})

def maintenance_request_create(request):
    if request.method == 'POST':
        form = MaintenanceRequestForm(request.POST)
        if form.is_valid():
            maintenance_instance = form.save(commit=False)
            if request.user.is_authenticated:
                User = get_user_model() # User model is imported at the top
                try:
                    actual_user = User.objects.get(pk=request.user.pk)
                    maintenance_instance.requester = actual_user # Gán thực thể User đầy đủ cho trường 'requester' như trong models.py
                    maintenance_instance.save()
                    # form.save_m2m() # Gọi nếu form có trường m2m và commit=False đã được sử dụng.
                    messages.success(request, 'Tạo yêu cầu bảo trì thành công!')
                    return redirect('maintenance_request_list')
                except User.DoesNotExist:
                    messages.error(request, "Người dùng báo cáo không hợp lệ.")
            else:
                messages.error(request, "Bạn cần đăng nhập để tạo yêu cầu.")
            # Nếu có lỗi xảy ra hoặc người dùng chưa xác thực, render lại form
            return render(request, 'maintenance/maintenance_request_form.html', {'form': form})
    else:
        form = MaintenanceRequestForm()
    return render(request, 'maintenance/maintenance_request_form.html', {'form': form})

def maintenance_request_update(request, pk):
    req = get_object_or_404(MaintenanceRequest, pk=pk)
    if request.method == 'POST':
        form = MaintenanceRequestForm(request.POST, instance=req)
        if form.is_valid():
            form.save()
            messages.success(request, 'Cập nhật yêu cầu bảo trì thành công!')
            return redirect('maintenance_request_list')
    else:
        form = MaintenanceRequestForm(instance=req)
    return render(request, 'maintenance/maintenance_request_form.html', {'form': form, 'object': req})

def maintenance_request_detail(request, pk):
    req = get_object_or_404(MaintenanceRequest, pk=pk)
    return render(request, 'maintenance/maintenance_request_detail.html', {'object': req})
