from django.db import models
from django.conf import settings
from devices.models import Device
from users.models import UserProfile

MAINTENANCE_STATUS_CHOICES = [
    ("pending", "Chờ xử lý"),
    ("in_progress", "Đang thực hiện"),
    ("completed", "Hoàn thành"),
    ("cancelled", "Đã hủy"),
]

class MaintenanceRequest(models.Model):
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name="maintenance_requests", verbose_name="Thiết bị")
    requester = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="requested_maintenances", verbose_name="Người yêu cầu")
    description = models.TextField(verbose_name="Mô tả sự cố")
    status = models.CharField(max_length=20, choices=MAINTENANCE_STATUS_CHOICES, default="pending", verbose_name="Trạng thái")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    assigned_to = models.ForeignKey(UserProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_maintenances", verbose_name="Kỹ thuật viên phụ trách")
    note = models.TextField(blank=True, null=True, verbose_name="Ghi chú xử lý")

    def __str__(self):
        return f"{self.device} - {self.get_status_display()}"

# Có thể mở rộng thêm các model khác cho lịch sử bảo trì, file đính kèm, đánh giá, ... nếu cần
