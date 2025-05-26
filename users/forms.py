from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import authenticate

User = get_user_model()

class UserRegisterForm(UserCreationForm):
    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']

    def save(self, commit=True):
        user = super().save(commit)
        # Tạo UserProfile với trạng thái chờ duyệt
        from .models import UserProfile
        profile, created = UserProfile.objects.get_or_create(user=user)
        profile.status = 'pending'  # Thay đổi từ is_approved=False sang status='pending'
        profile.save()

        # Tạo thông báo cho admin/staff về người dùng mới cần duyệt
        try:
            from bmsync.models import Notification
            from django.db.models import Q
            
            admins_and_staff = User.objects.filter(Q(is_superuser=True) | Q(is_staff=True))
            for admin_user in admins_and_staff:
                Notification.objects.create(
                    recipient=admin_user,
                    message=f"Người dùng mới '{user.username}' vừa đăng ký và cần được phê duyệt.",
                    notification_type='new_user',
                    related_object_id=user.pk
                )
        except Exception as e_notif_reg:
            print(f"Lỗi khi tạo thông báo đăng ký cho user {user.username}: {e_notif_reg}")

        return user

from django.contrib.auth import get_user_model, authenticate

class EmailAuthenticationForm(forms.Form):
    email = forms.EmailField(label='Email', max_length=254, widget=forms.EmailInput(attrs={'autofocus': True, 'placeholder': 'Nhập email'}))
    password = forms.CharField(label='Mật khẩu', strip=False, widget=forms.PasswordInput(attrs={'placeholder': 'Nhập mật khẩu'}))

    def clean(self):
        email = self.cleaned_data.get('email')
        password = self.cleaned_data.get('password')
        if email and password:
            User = get_user_model()
            users = User.objects.filter(email=email)
            print("[DEBUG] Số lượng user tìm thấy:", users.count())
            if not users.exists():
                print("[DEBUG] Không tìm thấy user với email này!")
                raise forms.ValidationError('Email không tồn tại.')
            if users.count() > 1:
                print("[DEBUG] Có nhiều user trùng email!")
                raise forms.ValidationError('Có nhiều tài khoản sử dụng cùng email này. Vui lòng liên hệ quản trị viên.')
            user = users.first()
            print("[DEBUG] Username tương ứng:", user.username)
            
            # Kiểm tra trạng thái tài khoản
            from users.models import UserProfile
            try:
                profile = UserProfile.objects.get(user=user)
                print("[DEBUG] Profile ID:", profile.id)
                print("[DEBUG] Trạng thái:", profile.status)
                print("[DEBUG] Trạng thái hoạt động (is_active):", user.is_active)
                print("[DEBUG] Vai trò:", profile.role_type)
                
                if profile.status == 'pending':
                    raise forms.ValidationError('Tài khoản này chưa được duyệt bởi quản trị viên.')
                elif profile.status == 'inactive':
                    raise forms.ValidationError('Tài khoản này đã bị khóa.')
            except UserProfile.DoesNotExist:
                print("[DEBUG] Không tìm thấy profile cho user này!")
                raise forms.ValidationError('Tài khoản chưa có profile, vui lòng liên hệ quản trị viên.')
            
            self.user_cache = authenticate(request=None, username=user.username, password=password)
            print("[DEBUG] Kết quả authenticate:", self.user_cache)
            if self.user_cache is None:
                raise forms.ValidationError('Sai mật khẩu.')
            return self.cleaned_data
        return self.cleaned_data

    def get_user(self):
        return getattr(self, 'user_cache', None)