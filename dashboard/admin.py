from django.contrib import admin
from .models import Device, MaintenanceRequest, MaintenanceTask, Report, DeviceRequest

@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ('name', 'device_type', 'status', 'location', 'last_updated')
    list_filter = ('status', 'device_type', 'location')
    search_fields = ('name', 'device_id', 'location')
    date_hierarchy = 'created_at'

@admin.register(MaintenanceRequest)
class MaintenanceRequestAdmin(admin.ModelAdmin):
    list_display = ('title', 'device', 'requester', 'priority', 'status', 'created_at')
    list_filter = ('status', 'priority')
    search_fields = ('title', 'description')
    date_hierarchy = 'created_at'

@admin.register(MaintenanceTask)
class MaintenanceTaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'maintenance_request', 'assigned_to', 'status', 'due_date', 'progress')
    list_filter = ('status', 'assigned_to')
    search_fields = ('title', 'description')
    date_hierarchy = 'created_at'

@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ('title', 'type', 'author', 'created_at')
    list_filter = ('type', 'author')
    search_fields = ('title', 'description')
    date_hierarchy = 'created_at'

@admin.register(DeviceRequest)
class DeviceRequestAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'location', 'requester', 'status', 'created_at')
    list_filter = ('status', 'type')
    search_fields = ('name', 'note')
    date_hierarchy = 'created_at' 