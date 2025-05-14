from django.contrib import admin
from .views import admin_dashboard # admin_dashboard đã được bảo vệ bằng @staff_member_required
from .models import User, Device, MaintenanceRequest

# Ghi đè view index mặc định của trang admin bằng view admin_dashboard tùy chỉnh
admin.site.index = admin_dashboard

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'is_active')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    list_filter = ('is_staff', 'is_active', 'groups')
    # Sắp xếp theo username để nhất quán
    ordering = ('username',)

@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ('device_id', 'name', 'device_type', 'status', 'location', 'purchase_date', 'next_maintenance_date')
    search_fields = ('device_id', 'name', 'location', 'description')
    list_filter = ('device_type', 'status', 'purchase_date', 'warranty_expiry_date', 'next_maintenance_date')
    fieldsets = (
        (None, {
            'fields': ('device_id', 'name', 'device_type', 'status', 'location')
        }),
        ('Thông tin mua hàng và bảo hành', {
            'fields': ('purchase_date', 'warranty_expiry_date'),
            'classes': ('collapse',)
        }),
        ('Thông tin bảo trì', {
            'fields': ('last_maintenance_date', 'next_maintenance_date'),
            'classes': ('collapse',)
        }),
        ('Mô tả chi tiết', {
            'fields': ('description',),
            'classes': ('collapse',)
        }),
    )
    date_hierarchy = 'purchase_date'
    ordering = ('-purchase_date', 'name')

@admin.register(MaintenanceRequest)
class MaintenanceRequestAdmin(admin.ModelAdmin):
    list_display = ('request_id', 'device_name', 'location', 'job_type', 'status', 'reported_by_username', 'report_date', 'assigned_to_username', 'priority', 'completion_date') # Thêm location, đổi request_type thành job_type
    search_fields = ('request_id', 'device__name', 'location', 'description', 'reported_by__username', 'assigned_to__username') # Thêm location
    list_filter = ('status', 'job_type', 'priority', 'report_date', 'completion_date') # Đổi request_type thành job_type
    autocomplete_fields = ['device', 'reported_by', 'assigned_to']
    # raw_id_fields = ('device', 'reported_by', 'assigned_to') # Sử dụng autocomplete_fields thay thế
    fieldsets = (
        ('Thông tin chung', {
            'fields': ('request_id', 'device', 'location', 'job_type', 'description', 'priority') # Thêm location, đổi request_type thành job_type
        }),
        ('Người liên quan và Thời gian', {
            'fields': ('reported_by', 'report_date', 'assigned_to', 'completion_date')
        }),
        ('Trạng thái và Ghi chú', {
            'fields': ('status', 'notes')
        }),
    )
    date_hierarchy = 'report_date'
    ordering = ('-report_date', 'priority')

    def device_name(self, obj):
        return obj.device.name if obj.device else 'N/A'
    device_name.short_description = 'Tên Thiết bị'

    def reported_by_username(self, obj):
        return obj.reported_by.username if obj.reported_by else 'N/A'
    reported_by_username.short_description = 'Người Báo Cáo'

    def assigned_to_username(self, obj):
        return obj.assigned_to.username if obj.assigned_to else 'N/A'
    assigned_to_username.short_description = 'Người Xử Lý'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Optimize query by prefetching related objects
        return qs.select_related('device', 'reported_by', 'assigned_to')