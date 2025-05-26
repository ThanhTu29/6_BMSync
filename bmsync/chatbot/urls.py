from django.urls import path
from . import views

urlpatterns = [
    path('chat/', views.chatbot_view, name='chatbot'),
    path('send_message/', views.send_message, name='send_message'),
]