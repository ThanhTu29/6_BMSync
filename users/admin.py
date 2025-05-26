from .models import Role, Permission, UserProfile
from django.contrib import admin
from django.contrib import messages

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
    list_display = ('user', 'role', 'status', 'phone', 'department')
    list_filter = ('role', 'status')
    search_fields = ('user__username', 'phone', 'department')
    actions = ['activate_users', 'deactivate_users']

    def activate_users(self, request, queryset):
        try:
            print("[DEBUG] Bắt đầu kích hoạt tài khoản...")
            for profile in queryset:
                print(f"[DEBUG] Đang kích hoạt profile ID {profile.id} của user {profile.user.username}")
                profile.status = 'active'
                profile.save()
                print(f"[DEBUG] Đã lưu trạng thái active cho profile ID {profile.id}")
            
            updated = queryset.count()
            self.message_user(request, f"Đã kích hoạt {updated} tài khoản thành công.", messages.SUCCESS)
            print(f"[DEBUG] Hoàn tất kích hoạt {updated} tài khoản")
        except Exception as e:
            print(f"[DEBUG] Lỗi khi kích hoạt tài khoản: {str(e)}")
            self.message_user(request, f"Lỗi khi kích hoạt tài khoản: {str(e)}", messages.ERROR)
    
    activate_users.short_description = "Kích hoạt các tài khoản được chọn"

    def deactivate_users(self, request, queryset):
        try:
            print("[DEBUG] Bắt đầu khóa tài khoản...")
            for profile in queryset:
                print(f"[DEBUG] Đang khóa profile ID {profile.id} của user {profile.user.username}")
                profile.status = 'inactive'
                profile.save()
                print(f"[DEBUG] Đã lưu trạng thái inactive cho profile ID {profile.id}")
            
            updated = queryset.count()
            self.message_user(request, f"Đã khóa {updated} tài khoản thành công.", messages.SUCCESS)
            print(f"[DEBUG] Hoàn tất khóa {updated} tài khoản")
        except Exception as e:
            print(f"[DEBUG] Lỗi khi khóa tài khoản: {str(e)}")
            self.message_user(request, f"Lỗi khi khóa tài khoản: {str(e)}", messages.ERROR)
    
    deactivate_users.short_description = "Khóa các tài khoản được chọn"
