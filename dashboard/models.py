from django.db import models
from django.utils import timezone
from users.models import UserProfile
from django.contrib.auth import get_user_model

User = get_user_model()

class Device(models.Model):
    DEVICE_TYPES = [
        ('ac', 'Air Conditioner'),
        ('light', 'Lighting'),
        ('security', 'Security System'),
        ('other', 'Other'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('maintenance', 'Under Maintenance'),
    ]
    
    device_id = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
    device_type = models.CharField(max_length=50, choices=DEVICE_TYPES)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES)
    location = models.CharField(max_length=100)
    manager = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='managed_devices')
    purchase_date = models.DateField(null=True, blank=True)
    warranty_expiry_date = models.DateField(null=True, blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_maintenance_date = models.DateTimeField(null=True, blank=True)
    next_maintenance_date = models.DateTimeField(null=True, blank=True)
    tenant = models.ForeignKey(UserProfile, on_delete=models.SET_NULL, null=True, related_name='devices')
    last_updated = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} ({self.device_id})"
    
    class Meta:
        verbose_name_plural = "Devices"

class MaintenanceRequest(models.Model):
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    title = models.CharField(max_length=200)
    description = models.TextField()
    device = models.ForeignKey(Device, on_delete=models.SET_NULL, null=True, blank=True, related_name='maintenance_requests')
    requester = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='maintenance_requests')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    assigned_to = models.ForeignKey(UserProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_maintenance_requests')
    
    def __str__(self):
        return f"{self.title} - {self.get_status_display()}"
    
    class Meta:
        verbose_name_plural = "Maintenance Requests"

class MaintenanceTask(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    title = models.CharField(max_length=200)
    description = models.TextField()
    maintenance_request = models.ForeignKey(MaintenanceRequest, on_delete=models.CASCADE, related_name='tasks')
    assigned_to = models.ForeignKey(UserProfile, on_delete=models.SET_NULL, null=True, related_name='maintenance_tasks')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    due_date = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    progress = models.PositiveSmallIntegerField(default=0, verbose_name='Tiến độ (%)')
    
    # Trường mới cho đánh giá
    rating = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        choices=[(i, str(i)) for i in range(1, 6)],  # 1 đến 5 sao
        verbose_name='Đánh giá (số sao)'
    )
    rating_comment = models.TextField(
        null=True,
        blank=True,
        verbose_name='Bình luận đánh giá'
    )
    rated_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Ngày đánh giá'
    )

    def __str__(self):
        return f"{self.title} - {self.get_status_display()}"
    
    class Meta:
        verbose_name_plural = "Maintenance Tasks"

class Report(models.Model):
    REPORT_TYPES = [
        ('maintenance', 'Maintenance Report'),
        ('device', 'Device Report'),
        ('system', 'System Report'),
    ]
    
    title = models.CharField(max_length=200)
    description = models.TextField()
    type = models.CharField(max_length=20, choices=REPORT_TYPES)
    author = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='reports')
    created_at = models.DateTimeField(auto_now_add=True)
    file = models.FileField(upload_to='reports/', null=True, blank=True)
    
    def __str__(self):
        return f"{self.title} - {self.get_type_display()}"
    
    class Meta:
        verbose_name_plural = "Reports"

class DeviceRequest(models.Model):
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=20)
    location = models.CharField(max_length=200)
    note = models.TextField(blank=True)
    requester = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='device_requests')
    status = models.CharField(max_length=20, choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')], default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    def __str__(self):
        return f"Yêu cầu thêm thiết bị: {self.name} - {self.get_status_display()}"
    class Meta:
        verbose_name_plural = "Device Requests" 