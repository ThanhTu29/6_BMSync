from django.db import models
from django.conf import settings

class Role(models.Model):
    name = models.CharField(max_length=50, unique=True, verbose_name="Tên vai trò")
    description = models.TextField(blank=True, null=True, verbose_name="Mô tả")
    def __str__(self):
        return self.name

class Permission(models.Model):
    code = models.CharField(max_length=50, unique=True, verbose_name="Mã quyền")
    name = models.CharField(max_length=100, verbose_name="Tên quyền")
    description = models.TextField(blank=True, null=True, verbose_name="Mô tả")
    def __str__(self):
        return self.name

class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile", verbose_name="Tài khoản")

    role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Vai trò")
    permissions = models.ManyToManyField(Permission, blank=True, verbose_name="Các quyền bổ sung")
    phone = models.CharField(max_length=20, blank=True, null=True, verbose_name="Số điện thoại")
    department = models.CharField(max_length=100, blank=True, null=True, verbose_name="Phòng ban")
    is_approved = models.BooleanField(default=False, verbose_name="Đã được duyệt bởi admin")
    def __str__(self):
        return self.user.username

# Có thể mở rộng thêm các trường khác cho UserProfile nếu cần
