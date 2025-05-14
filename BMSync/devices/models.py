from django.db import models

DEVICE_STATUS_CHOICES = [
    ("active", "Hoạt động"),
    ("broken", "Hỏng"),
    ("maintenance", "Đang bảo trì"),
]

DEVICE_GROUP_CHOICES = [
    ("office", "Thiết bị văn phòng"),
    ("classroom", "Thiết bị phòng học"),
    ("common", "Thiết bị chung"),
]

class Device(models.Model):
    code = models.CharField(max_length=50, unique=True, verbose_name="Mã thiết bị")
    name = models.CharField(max_length=255, verbose_name="Tên thiết bị")
    device_type = models.CharField(max_length=100, verbose_name="Loại thiết bị")
    group = models.CharField(max_length=20, choices=DEVICE_GROUP_CHOICES, verbose_name="Nhóm thiết bị")
    status = models.CharField(max_length=20, choices=DEVICE_STATUS_CHOICES, default="active", verbose_name="Trạng thái")
    location = models.ForeignKey('locations.Room', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Vị trí (Phòng)")
    description = models.TextField(blank=True, null=True, verbose_name="Mô tả")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.code} - {self.name}"
