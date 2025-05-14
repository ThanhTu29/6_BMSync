from django.contrib import admin
from django.urls import path, include
from . import views

urlpatterns = [
    # Custom admin paths FIRST
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin/quan-ly-thiet-bi/', views.admin_quan_ly_thiet_bi, name='admin_quan_ly_thiet_bi'),
    path('admin/quan-ly-thiet-bi/them/', views.admin_them_thiet_bi, name='admin_them_thiet_bi'), # Giả sử có view này hoặc sẽ tạo
    path('admin/quan-ly-thiet-bi/sua/<int:device_id>/', views.admin_sua_thiet_bi, name='admin_sua_thiet_bi'),
    path('admin/quan-ly-thiet-bi/xoa/<int:device_id>/', views.admin_xoa_thiet_bi, name='admin_xoa_thiet_bi'),
    path('admin/quan-ly-nguoi-dung/', views.admin_quan_ly_nguoi_dung, name='admin_quan_ly_nguoi_dung'),
    path('admin/quan-ly-nguoi-dung/them/', views.admin_them_nguoi_dung, name='admin_them_nguoi_dung'),
    path('admin/quan-ly-nguoi-dung/sua/<int:user_id>/', views.admin_sua_nguoi_dung, name='admin_sua_nguoi_dung'),
    path('admin/quan-ly-nguoi-dung/xoa/<int:user_id>/', views.admin_xoa_nguoi_dung, name='admin_xoa_nguoi_dung'),
    path('admin/phieu-muon-bao-tri/', views.admin_phieu_muon_bao_tri, name='admin_phieu_muon_bao_tri'),
    path('admin/phieu-muon-bao-tri/them/', views.admin_them_phieu_muon_bao_tri, name='admin_them_phieu_muon_bao_tri'),
    path('admin/phieu-muon-bao-tri/sua/<str:request_id>/', views.admin_sua_phieu_muon_bao_tri, name='admin_sua_phieu_muon_bao_tri'),
    path('admin/phieu-muon-bao-tri/xoa/<str:request_id>/', views.admin_xoa_phieu_muon_bao_tri, name='admin_xoa_phieu_muon_bao_tri'),
    path('admin/phieu-muon-bao-tri/send-notification/<str:request_id>/', views.send_maintenance_notification, name='send_maintenance_notification'), # Added this line
    path('admin/tong-hop-bao-cao/', views.admin_tong_hop_bao_cao, name='admin_tong_hop_bao_cao'),
    path('admin/chatbot/', views.admin_chatbot, name='admin_chatbot'),
    path('admin/thong-bao/', views.admin_thong_bao, name='admin_thong_bao'),
    path('admin/notifications/mark-as-read/<int:notification_id>/', views.mark_notification_as_read, name='mark_notification_as_read'),
    path('admin/notifications/mark-all-as-read/', views.mark_all_notifications_as_read, name='mark_all_notifications_as_read'),
    path('admin/bao-mat/', views.admin_bao_mat, name='admin_bao_mat'),
    path('admin/bao-mat/change-password/', views.admin_change_password, name='admin_change_password'),
    path('admin/bao-mat/logout-other-devices/', views.admin_logout_other_devices, name='admin_logout_other_devices'),
    path('admin/cai-dat/', views.admin_cai_dat, name='admin_cai_dat'),
    path('admin/ho-tro/', views.admin_ho_tro, name='admin_ho_tro'),

    # Django's built-in admin
    path('admin/', admin.site.urls),

    # Other app paths
    path('chat/', include('chatbot.urls')),
    path('', views.base_view, name='home'),
    path('users/', include('users.urls')),
    path('maintenance/', include('maintenance.urls')),
    path('developing/', views.developing_view, name='developing'),
    path('account/', lambda request: __import__('django.shortcuts').shortcuts.redirect('/users/account/')),
    # URLs for notification and password change
    path('notifications/mark-read/<int:notification_id>/', views.mark_notification_as_read, name='bmsync_mark_notification_read'),
    path('notifications/', views.user_notifications_view, name='user_notifications'), # URL cho trang thông báo người dùng
    path('account/change-password/', views.change_password, name='bmsync_change_password'),

    path('gioi-thieu/', views.about_view, name='about'),
    path('dich-vu/', views.services_view, name='services'),
    path('lien-he/', views.contact_view, name='contact'),
    path('settings/', views.settings_view, name='settings'), # URL for settings page
]
