from django.urls import path, include
from . import views

urlpatterns = [
    path('', views.maintenance_request_list, name='maintenance_request_list'),
    path('create/', views.maintenance_request_create, name='maintenance_request_create'),
    path('<int:pk>/update/', views.maintenance_request_update, name='maintenance_request_update'),
    path('<int:pk>/', views.maintenance_request_detail, name='maintenance_request_detail'),
]