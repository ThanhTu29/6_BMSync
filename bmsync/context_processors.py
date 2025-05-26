from .models import Notification

def unread_notifications_count(request):
    if hasattr(request, 'user') and request.user.is_authenticated:
        try:
            count = Notification.objects.filter(recipient=request.user, is_read=False).count()
            return {'unread_notifications_count': count}
        except Exception:
            # Fallback to 0 if any error occurs during the query
            return {'unread_notifications_count': 0}
    return {'unread_notifications_count': 0}