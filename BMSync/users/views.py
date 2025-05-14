from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm
from .forms import UserRegisterForm, EmailAuthenticationForm
from bmsync.models import Notification # Đảm bảo import ở đầu file nếu chưa có
from django.contrib import messages

def register_view(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Đăng ký thành công! Bạn có thể đăng nhập.')
            return redirect('login')
    else:
        form = UserRegisterForm()
    return render(request, 'users/register.html', {'form': form})

def login_view(request):
    if request.method == 'POST':
        form = EmailAuthenticationForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            if user is not None:
                login(request, user)
                if user.is_superuser or user.is_staff:
                    messages.success(request, 'Đăng nhập thành công với quyền admin!')
                    return redirect('admin:index')
                else:
                    messages.success(request, 'Đăng nhập thành công!')
                    return redirect('home')
            else:
                messages.error(request, 'Email hoặc mật khẩu không đúng!')
        else:
            messages.error(request, 'Vui lòng kiểm tra lại thông tin đăng nhập!')
    else:
        form = EmailAuthenticationForm()
    return render(request, 'users/login.html', {'form': form})

from django.contrib.auth import logout
from django.shortcuts import redirect
from django.contrib import messages

def logout_view(request):
    logout(request)
    messages.success(request, 'Bạn đã đăng xuất thành công.')
    return redirect('login')

def account_info_view(request):
    if not request.user.is_authenticated:
        from django.shortcuts import redirect
        return redirect('login')
    
    base_template = 'admin/admin_base.html' if request.user.is_staff else 'base.html'
    # Đếm số thông báo chưa đọc cho admin_base template (nếu cần thiết ở đây, thường là trong context processor)
    unread_notifications_count = 0
    if request.user.is_staff:
        from bmsync.models import Notification # Cần import Notification
        unread_notifications_count = Notification.objects.filter(recipient=request.user, is_read=False).count()

    return render(request, 'users/account_info.html', {
        'base_template_to_extend': base_template,
        'unread_notifications_count': unread_notifications_count # Truyền cho admin_base nếu nó dùng
        })