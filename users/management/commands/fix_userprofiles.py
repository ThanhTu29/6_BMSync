from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from users.models import UserProfile

class Command(BaseCommand):
    help = "Tạo UserProfile cho mọi user chưa có profile"

    def handle(self, *args, **kwargs):
        User = get_user_model()
        created = 0
        for user in User.objects.all():
            if not hasattr(user, 'profile'):
                UserProfile.objects.create(
                    user=user,
                    role_type='tenant',
                    status='active'
                )
                created += 1
        self.stdout.write(self.style.SUCCESS(f"Đã tạo {created} UserProfile cho user chưa có profile.")) 