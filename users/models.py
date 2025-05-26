from django.db import models
from django.conf import settings
from django.contrib.auth.models import Group
from django.db.models.signals import post_save
from django.dispatch import receiver

class Role(models.Model):
    name = models.CharField(max_length=50, unique=True, verbose_name="Tên vai trò")
    description = models.TextField(blank=True, null=True, verbose_name="Mô tả")
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = "Vai trò"
        verbose_name_plural = "Vai trò"

class Permission(models.Model):
    code = models.CharField(max_length=50, unique=True, verbose_name="Mã quyền")
    name = models.CharField(max_length=100, verbose_name="Tên quyền")
    description = models.TextField(blank=True, null=True, verbose_name="Mô tả")
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = "Quyền"
        verbose_name_plural = "Quyền"

class UserProfile(models.Model):
    ROLE_CHOICES = (
        ('maintenance', 'Maintenance'),
        ('manager', 'Manager'),
        ('tenant', 'Tenant'),
    )
    
    STATUS_CHOICES = (
        ('active', 'Hoạt động'),
        ('inactive', 'Khóa'),
        ('pending', 'Chờ Admin xác nhận'),
    )
    
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile", verbose_name="Tài khoản")
    role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Vai trò")
    permissions = models.ManyToManyField(Permission, blank=True, verbose_name="Các quyền bổ sung")
    phone = models.CharField(max_length=20, blank=True, null=True, verbose_name="Số điện thoại")
    department = models.CharField(max_length=100, blank=True, null=True, verbose_name="Phòng ban")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="Trạng thái")
    
    # Thêm các trường mới
    role_type = models.CharField(max_length=20, choices=ROLE_CHOICES, default='tenant', verbose_name="Loại vai trò")
    last_login_ip = models.GenericIPAddressField(null=True, blank=True, verbose_name="IP đăng nhập cuối")
    last_activity = models.DateTimeField(null=True, blank=True, verbose_name="Hoạt động cuối")
    
    def __str__(self):
        return f"{self.user.username} - {self.get_role_type_display()}"
    
    @property
    def is_approved(self):
        return self.status == 'active'
    
    def has_role(self, role_name):
        """Kiểm tra xem người dùng có vai trò cụ thể không"""
        return self.role_type == role_name
    
    def get_dashboard_template(self):
        """Trả về template dashboard tương ứng với vai trò"""
        return f"dashboard/{self.role_type}_dashboard.html"
    
    def get_available_permissions(self):
        """Trả về danh sách các quyền có sẵn cho vai trò"""
        return self.permissions.all()
    
    def is_maintenance(self):
        return self.role_type == 'maintenance'
    
    def is_manager(self):
        return self.role_type == 'manager'
    
    def is_tenant(self):
        return self.role_type == 'tenant'
    
    class Meta:
        verbose_name = "Thông tin người dùng"
        verbose_name_plural = "Thông tin người dùng"

# Có thể mở rộng thêm các trường khác cho UserProfile nếu cần

@receiver(post_save, sender=UserProfile)
def sync_role_type(sender, instance, **kwargs):
    if instance.role:
        role_name = instance.role.name.strip().lower()
        if role_name == 'manager' and instance.role_type != 'manager':
            instance.role_type = 'manager'
            instance.save(update_fields=['role_type'])
        elif role_name == 'tenant' and instance.role_type != 'tenant':
            instance.role_type = 'tenant'
            instance.save(update_fields=['role_type'])
        elif role_name == 'maintenance' and instance.role_type != 'maintenance':
            instance.role_type = 'maintenance'
            instance.save(update_fields=['role_type'])
