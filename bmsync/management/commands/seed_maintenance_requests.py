import random
from django.core.management.base import BaseCommand
from django.utils import timezone
from bmsync.models import Device, MaintenanceRequest, User
from django.contrib.auth.models import Group

class Command(BaseCommand):
    help = 'Seeds the database with sample maintenance requests.'

    def handle(self, *args, **options):
        self.stdout.write('Seeding maintenance requests...')

        # Ensure groups exist
        tenant_group, _ = Group.objects.get_or_create(name='Tenant')
        staff_group, _ = Group.objects.get_or_create(name='Maintenance Staff')
        admin_group, _ = Group.objects.get_or_create(name='Admin')

        # Get or create sample users
        reporter1, _ = User.objects.get_or_create(
            username='tenant_reporter1',
            defaults={'email': 'reporter1@example.com', 'first_name': 'Reporter', 'last_name': 'One'}
        )
        reporter1.groups.add(tenant_group)
        reporter1.save()

        reporter2, _ = User.objects.get_or_create(
            username='tenant_reporter2',
            defaults={'email': 'reporter2@example.com', 'first_name': 'Reporter', 'last_name': 'Two'}
        )
        reporter2.groups.add(tenant_group)
        reporter2.save()

        technician1, _ = User.objects.get_or_create(
            username='maint_staff1',
            defaults={'email': 'tech1@example.com', 'first_name': 'Technician', 'last_name': 'Alpha', 'is_staff': True}
        )
        technician1.groups.add(staff_group)
        technician1.save()

        technician2, _ = User.objects.get_or_create(
            username='maint_staff2',
            defaults={'email': 'tech2@example.com', 'first_name': 'Technician', 'last_name': 'Beta', 'is_staff': True}
        )
        technician2.groups.add(staff_group)
        technician2.save()
        
        admin_user, _ = User.objects.get_or_create(
            username='admin_reporter',
            defaults={'email': 'admin_reporter@example.com', 'is_staff': True, 'is_superuser': True}
        )
        admin_user.groups.add(admin_group)
        admin_user.save()

        reporters = [reporter1, reporter2, admin_user]
        technicians = [technician1, technician2, None] # Include None for unassigned

        devices = list(Device.objects.all())
        if not devices:
            # Create some dummy devices if none exist
            Device.objects.create(device_id='DEV001', name='Laptop Dell XPS 13', device_type='laptop', status='active', location='A.1')
            Device.objects.create(device_id='DEV002', name='Printer HP LaserJet', device_type='printer', status='active', location='B.2')
            Device.objects.create(device_id='DEV003', name='Monitor Samsung 27inch', device_type='monitor', status='maintenance', location='C.1')
            devices = list(Device.objects.all())
        
        if not devices:
            self.stdout.write(self.style.WARNING('No devices found. Please seed devices first or add some manually. Skipping maintenance request seeding for now.'))
            return

        request_types = [choice[0] for choice in MaintenanceRequest.REQUEST_TYPE_CHOICES]
        statuses = [choice[0] for choice in MaintenanceRequest.STATUS_CHOICES]
        priorities = [1, 2, 3]

        descriptions = [
            'Màn hình bị nhấp nháy liên tục.',
            'Máy in không kéo được giấy.',
            'Cần mượn máy chiếu cho cuộc họp chiều nay.',
            'Bàn phím laptop bị kẹt vài nút.',
            'Chuột không dây hết pin, cần thay.',
            'Yêu cầu kiểm tra định kỳ máy chủ.',
            'Phần mềm X bị lỗi, không khởi động được.',
            'Cần cài đặt driver cho máy scan mới.',
            'Mạng LAN chập chờn, kết nối không ổn định.',
            'Yêu cầu hỗ trợ di chuyển thiết bị sang phòng mới.'
        ]

        MaintenanceRequest.objects.all().delete() # Clear existing requests before seeding
        self.stdout.write('Cleared existing maintenance requests.')

        for i in range(10): # Create 10 sample requests
            device = random.choice(devices) if devices else None
            reported_by_user = random.choice(reporters)
            assigned_to_user = random.choice(technicians)
            
            # Ensure assigned_to is None if status is 'new' or 'completed' or 'cancelled' for realism
            current_status = random.choice(statuses)
            if current_status in ['new', 'completed', 'cancelled']:
                assigned_to_user = None
            elif current_status in ['assigned', 'in_progress'] and assigned_to_user is None and technicians:
                # if it's assigned or in_progress, it should have an assignee if possible
                assignable_techs = [t for t in technicians if t is not None]
                if assignable_techs:
                    assigned_to_user = random.choice(assignable_techs)

            request_id_num = MaintenanceRequest.objects.count() + 1
            MaintenanceRequest.objects.create(
                request_id=f'REQ{timezone.now().strftime("%Y%m%d")}{request_id_num:03d}',
                device=device,
                request_type=random.choice(request_types),
                description=random.choice(descriptions),
                reported_by=reported_by_user,
                assigned_to=assigned_to_user,
                status=current_status,
                report_date=timezone.now() - timezone.timedelta(days=random.randint(0, 30)),
                completion_date=timezone.now() if current_status == 'completed' else None,
                priority=random.choice(priorities),
                notes='Đây là ghi chú mẫu cho yêu cầu.' if random.choice([True, False]) else None
            )
        self.stdout.write(self.style.SUCCESS('Successfully seeded 10 maintenance requests.'))