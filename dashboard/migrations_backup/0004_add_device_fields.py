# Generated manually

from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings
from django.utils import timezone


def clean_invalid_managers(apps, schema_editor):
    Device = apps.get_model('dashboard', 'Device')
    User = apps.get_model(settings.AUTH_USER_MODEL.split('.')[0], settings.AUTH_USER_MODEL.split('.')[1])
    valid_user_ids = User.objects.values_list('id', flat=True)
    
    # Set manager to NULL for devices with invalid manager_id
    Device.objects.exclude(manager_id__in=valid_user_ids).update(manager=None)


def generate_device_ids(apps, schema_editor):
    Device = apps.get_model('dashboard', 'Device')
    for device in Device.objects.all():
        device.device_id = f'VP-{device.id:03d}'  # Format: VP-001, VP-002, etc.
        device.save()


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0003_devicerequest'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # First add device_id as nullable
        migrations.AddField(
            model_name='device',
            name='device_id',
            field=models.CharField(max_length=50, null=True),
        ),
        # Add manager field
        migrations.AddField(
            model_name='device',
            name='manager',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='managed_devices', to=settings.AUTH_USER_MODEL),
        ),
        # Clean invalid manager references
        migrations.RunPython(clean_invalid_managers),
        # Add created_at and updated_at fields
        migrations.AddField(
            model_name='device',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, default=timezone.now),
        ),
        migrations.AddField(
            model_name='device',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
        # Add other fields
        migrations.AddField(
            model_name='device',
            name='description',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='device',
            name='purchase_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='device',
            name='warranty_expiry_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='device',
            name='last_maintenance_date',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='device',
            name='next_maintenance_date',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RenameField(
            model_name='device',
            old_name='type',
            new_name='device_type',
        ),
        # Run data migration to generate device_ids
        migrations.RunPython(generate_device_ids),
        # Make device_id unique and non-nullable
        migrations.AlterField(
            model_name='device',
            name='device_id',
            field=models.CharField(max_length=50, unique=True),
        ),
    ] 