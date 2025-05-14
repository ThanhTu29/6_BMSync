import random
from django.core.management.base import BaseCommand
from bmsync.models import Device
from django.utils import timezone
from datetime import timedelta

class Command(BaseCommand):
    help = 'Seeds the database with initial device data'

    def handle(self, *args, **options):
        self.stdout.write('Deleting existing devices...')
        Device.objects.all().delete()
        self.stdout.write(self.style.SUCCESS('Successfully deleted existing devices.'))

        self.stdout.write('Seeding new devices...')

        device_types_available = [choice[0] for choice in Device.TYPE_CHOICES if choice[0] != 'other']
        if not device_types_available:
            self.stdout.write(self.style.ERROR('No device types available in Device.TYPE_CHOICES. Please define them in models.py'))
            return

        locations_prefixes = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
        statuses = [choice[0] for choice in Device.STATUS_CHOICES]

        devices_to_create = []
        for i in range(30):
            device_type = random.choice(device_types_available)
            location_prefix = random.choice(locations_prefixes)
            location_number = random.randint(1, 5)
            location = f'{location_prefix}.{location_number}'
            
            purchase_days_ago = random.randint(30, 365 * 3) # Purchased within last 3 years
            purchase_date = timezone.now().date() - timedelta(days=purchase_days_ago)
            
            warranty_days = random.randint(180, 365 * 2) # Warranty between 6 months to 2 years
            warranty_expiry_date = purchase_date + timedelta(days=warranty_days)
            
            last_maintenance_days_ago = random.randint(10, 180) if random.choice([True, False]) else None
            last_maintenance_date = purchase_date + timedelta(days=random.randint(1, purchase_days_ago - 10)) if last_maintenance_days_ago else None
            
            next_maintenance_days = random.randint(30, 180) if last_maintenance_date else random.randint(90, 365)
            next_maintenance_date = (last_maintenance_date + timedelta(days=next_maintenance_days)) if last_maintenance_date else (purchase_date + timedelta(days=next_maintenance_days))

            device_name_map = {
                'desktop_pc': 'Máy tính để bàn Dell Optiplex',
                'laptop': 'Laptop HP Elitebook',
                'monitor': 'Màn hình Samsung 24 inch',
                'printer': 'Máy in Canon LBP2900',
                'photocopier': 'Máy Photocopy Ricoh Aficio',
                'projector': 'Máy chiếu Epson EB-X05',
                'desk_phone': 'Điện thoại bàn Panasonic',
                'network_device': 'Router Cisco RV340',
                'scanner': 'Máy Scan HP ScanJet',
                'ups': 'Bộ lưu điện APC BX650',
                'server': 'Máy chủ Dell PowerEdge',
                'storage': 'Thiết bị lưu trữ NAS Synology'
            }
            base_name = device_name_map.get(device_type, 'Thiết bị Văn Phòng')

            devices_to_create.append(
                Device(
                    device_id=f'VP-{str(i+1).zfill(3)}',
                    name=f'{base_name} #{i+1}',
                    device_type=device_type,
                    status=random.choice(statuses),
                    location=location,
                    purchase_date=purchase_date,
                    warranty_expiry_date=warranty_expiry_date,
                    description=f'Mô tả ngắn gọn cho {base_name} #{i+1} tại vị trí {location}.',
                    last_maintenance_date=last_maintenance_date,
                    next_maintenance_date=next_maintenance_date
                )
            )
        
        Device.objects.bulk_create(devices_to_create)
        self.stdout.write(self.style.SUCCESS(f'Successfully seeded {len(devices_to_create)} devices.'))