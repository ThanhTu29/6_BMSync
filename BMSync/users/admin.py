from .models import Role, Permission, UserProfile
from django.contrib import admin

@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)

@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'description')
    search_fields = ('code', 'name')

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'is_approved', 'phone', 'department')
    list_filter = ('role', 'is_approved')
    search_fields = ('user__username', 'phone', 'department')
    actions = ['approve_users']

    def approve_users(self, request, queryset):
        updated = queryset.update(is_approved=True)
        self.message_user(request, f"Đã duyệt {updated} tài khoản thành công.")
    approve_users.short_description = "Duyệt các tài khoản được chọn"
