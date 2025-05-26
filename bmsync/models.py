from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.conf import settings

class User(AbstractUser):
    groups = models.ManyToManyField(
        'auth.Group',
        verbose_name='groups',
        blank=True,
        help_text='The groups this user belongs to. A user will get all permissions granted to each of their groups.',
        related_name="bmsync_user_set",  # Đã thay đổi related_name
        related_query_name="user",
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        verbose_name='user permissions',
        blank=True,
        help_text='Specific permissions for this user.',
        related_name="bmsync_user_permissions_set",  # Đã thay đổi related_name
        related_query_name="user",
    )
    # Thêm các trường tùy chỉnh cho User nếu cần
    # ví dụ: phone_number = models.CharField(max_length=15, blank=True, null=True)
    department = models.CharField(max_length=100, blank=True, null=True, verbose_name='Phòng ban')

    ACCOUNT_STATUS_CHOICES = [
        ('active', 'Hoạt động'),
        ('locked', 'Khóa'),
        ('pending', 'Chờ Xác nhận'),
    ]
    account_status = models.CharField(
        max_length=20,
        choices=ACCOUNT_STATUS_CHOICES,
        default='pending',
        verbose_name='Trạng thái tài khoản'
    )

    def save(self, *args, **kwargs):
        if self.account_status == 'locked':
            self.is_active = False
        else:
            self.is_active = True # pending and active users are is_active = True
        super().save(*args, **kwargs)

    pass

class Device(models.Model):
    STATUS_CHOICES = [
        ('active', 'Đang hoạt động'),
        ('maintenance', 'Đang bảo trì'),
        ('inactive', 'Không hoạt động'),
        ('broken', 'Hỏng'),
        ('in_storage', 'Lưu kho'),
    ]
    TYPE_CHOICES = [
        ('desktop_pc', 'Máy tính để bàn'),
        ('laptop', 'Máy tính xách tay'),
        ('monitor', 'Màn hình máy tính'),
        ('printer', 'Máy in'),
        ('photocopier', 'Máy photocopy'),
        ('projector', 'Máy chiếu'),
        ('desk_phone', 'Điện thoại bàn'),
        ('network_device', 'Thiết bị mạng (Router/Switch)'),
        ('scanner', 'Máy scan'),
        ('ups', 'Bộ lưu điện (UPS)'),
        ('server', 'Máy chủ'),
        ('storage', 'Thiết bị lưu trữ'),
        ('other', 'Khác'),
    ]

    device_id = models.CharField(max_length=50, unique=True, verbose_name='ID Thiết bị')
    name = models.CharField(max_length=200, verbose_name='Tên Thiết bị')
    device_type = models.CharField(max_length=50, choices=TYPE_CHOICES, verbose_name='Loại')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active', verbose_name='Trạng thái')
    location = models.CharField(max_length=100, blank=True, null=True, verbose_name='Vị trí')
    purchase_date = models.DateField(blank=True, null=True, verbose_name='Ngày mua')
    warranty_expiry_date = models.DateField(blank=True, null=True, verbose_name='Ngày hết hạn bảo hành')
    description = models.TextField(blank=True, null=True, verbose_name='Mô tả')
    last_maintenance_date = models.DateField(blank=True, null=True, verbose_name='Ngày bảo trì cuối')
    next_maintenance_date = models.DateField(blank=True, null=True, verbose_name='Ngày bảo trì kế tiếp')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.device_id} - {self.name}"

    class Meta:
        verbose_name = 'Thiết bị'
        verbose_name_plural = 'Thiết bị'

class MaintenanceRequest(models.Model):
    STATUS_CHOICES = [
        ('new', 'Mới'),
        ('assigned', 'Đã giao'),
        ('in_progress', 'Đang xử lý'),
        ('completed', 'Hoàn thành'),
        ('cancelled', 'Đã hủy'),
    ]
    JOB_TYPE_CHOICES = [
        ('loan', 'Mượn'),
        ('maintenance', 'Bảo trì'),
    ]
    NOTIFICATION_STATUS_CHOICES = [
        ('not_sent', 'Chưa gửi'),
        ('sent', 'Đã gửi'),
    ]

    request_id = models.CharField(max_length=50, unique=True, verbose_name='ID Yêu cầu')
    device = models.ForeignKey(Device, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Thiết bị')
    location = models.CharField(max_length=255, verbose_name='Vị trí', blank=True, null=True) # Thêm trường Vị trí
    job_type = models.CharField(max_length=20, choices=JOB_TYPE_CHOICES, default='maintenance', verbose_name='Công việc') # Đổi tên và cập nhật choices
    description = models.TextField(verbose_name='Mô tả')
    reported_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='reported_requests_v2', verbose_name='Người báo cáo') # Changed to direct User model and new related_name
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_requests_v2', verbose_name='Người xử lý') # Changed to direct User model and new related_name
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new', verbose_name='Trạng thái')
    report_date = models.DateTimeField(default=timezone.now, verbose_name='Ngày báo cáo')
    completion_date = models.DateTimeField(blank=True, null=True, verbose_name='Ngày hoàn thành')
    priority = models.IntegerField(default=3, help_text='1=Cao, 2=Trung bình, 3=Thấp', verbose_name='Độ ưu tiên')
    notes = models.TextField(blank=True, null=True, verbose_name='Ghi chú')
    notification_status = models.CharField(
        max_length=10, 
        choices=NOTIFICATION_STATUS_CHOICES, 
        default='not_sent', 
        verbose_name='Trạng thái thông báo'
    )

    def __str__(self):
        return f"{self.request_id} - {self.get_job_type_display()} cho {self.device.name if self.device else 'N/A'} tại {self.location if self.location else 'N/A'}"

    class Meta:
        verbose_name = 'Yêu cầu Công việc'
        verbose_name_plural = 'Các Yêu cầu Công việc'
        ordering = ['-report_date']

# Bạn có thể thêm các model khác nếu cần, ví dụ:
# class LoanTicket(models.Model): ...
class Notification(models.Model):
    USER_ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('manager', 'Manager'),
        ('maintenance_staff', 'Maintenance Staff'),
        ('tenant', 'Tenant'),
    ]
    NOTIFICATION_TYPE_CHOICES = [
        ('new_user', 'Người dùng mới cần xác nhận'),
        ('new_request', 'Yêu cầu mới (mượn/bảo trì)'),
        ('request_processed', 'Yêu cầu đã xử lý'),
        ('task_assigned', 'Công việc được giao'),
        ('task_completed', 'Công việc đã hoàn thành'),
        ('warranty_reminder', 'Nhắc nhở hết hạn bảo hành thiết bị'),
        ('maintenance_reminder', 'Nhắc nhở lịch bảo trì thiết bị'),
        ('other', 'Khác'),
    ]

    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications', verbose_name='Người nhận')
    message = models.TextField(verbose_name='Nội dung thông báo')
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name='Thời gian')
    is_read = models.BooleanField(default=False, verbose_name='Đã đọc')
    notification_type = models.CharField(max_length=50, choices=NOTIFICATION_TYPE_CHOICES, verbose_name='Loại thông báo')
    related_object_id = models.PositiveIntegerField(null=True, blank=True, verbose_name='ID đối tượng liên quan') # ID của User, Device, MaintenanceRequest, ...
    # Để biết loại đối tượng liên quan, có thể thêm một trường contentType
    # from django.contrib.contenttypes.models import ContentType
    # related_object_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return f"Thông báo cho {self.recipient.username} - {self.get_notification_type_display()}"

    class Meta:
        verbose_name = 'Thông báo'
        verbose_name_plural = 'Thông báo'
        ordering = ['-timestamp']

# class Report(models.Model): ...
# class Report(models.Model): ...