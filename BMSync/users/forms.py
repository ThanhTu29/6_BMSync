from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import authenticate

class UserRegisterForm(UserCreationForm):
    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']

    def save(self, commit=True):
        user = super().save(commit)
        # Tạo UserProfile với trạng thái chờ duyệt
        from .models import UserProfile
        profile, created = UserProfile.objects.get_or_create(user=user)
        profile.is_approved = False
        profile.save()

        # Tạo thông báo cho admin/staff về người dùng mới cần duyệt
        try:
            from bmsync.models import Notification, User as BmsyncUser # Sử dụng alias để tránh xung đột với User từ auth.models
            from django.db.models import Q
            
            admins_and_staff = BmsyncUser.objects.filter(Q(is_superuser=True) | Q(is_staff=True))
            for admin_user in admins_and_staff:
                Notification.objects.create(
                    recipient=admin_user,
                    message=f"Người dùng mới '{user.username}' vừa đăng ký và cần được phê duyệt.",
                    notification_type='new_user',
                    related_object_id=user.pk
                )
        except Exception as e_notif_reg:
            # Ghi log lỗi nếu có, nhưng không làm gián đoạn quá trình đăng ký
            print(f"Lỗi khi tạo thông báo đăng ký cho user {user.username}: {e_notif_reg}") 
            # import logging
            # logger = logging.getLogger(__name__)
            # logger.error(f"Lỗi khi tạo thông báo đăng ký cho user {user.username}: {e_notif_reg}", exc_info=True)

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
            # Kiểm tra trạng thái duyệt tài khoản
            if hasattr(user, 'profile') and hasattr(user.profile, 'is_approved'):
                print("[DEBUG] Trạng thái duyệt:", user.profile.is_approved)
                if not user.profile.is_approved:
                    raise forms.ValidationError('Tài khoản này chưa được duyệt bởi quản trị viên.')
            self.user_cache = authenticate(request=None, username=user.username, password=password)
            print("[DEBUG] Kết quả authenticate:", self.user_cache)
            if self.user_cache is None:
                print("[DEBUG] Sai mật khẩu hoặc user không tồn tại!")
                raise forms.ValidationError('Email hoặc mật khẩu không đúng.')
            elif not self.user_cache.is_active:
                print("[DEBUG] Tài khoản bị khóa!")
                raise forms.ValidationError('Tài khoản này đã bị khóa.')
        return self.cleaned_data

    def get_user(self):
        return getattr(self, 'user_cache', None)