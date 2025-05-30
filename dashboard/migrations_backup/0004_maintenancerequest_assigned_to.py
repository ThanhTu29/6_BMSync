# Generated by Django 5.0.2 on 2025-05-20 20:41

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0003_devicerequest'),
        ('users', '0002_alter_permission_options_alter_role_options_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='maintenancerequest',
            name='assigned_to',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='assigned_maintenance_requests', to='users.userprofile'),
        ),
    ]
