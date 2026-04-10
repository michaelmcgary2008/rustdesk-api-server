# Generated manually for MachineGroup and RustDeskPeer.machine_group

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0008_rustdesdevice_ip_address'),
    ]

    operations = [
        migrations.CreateModel(
            name='MachineGroup',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=80, verbose_name='Group name')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='machine_groups', to=settings.AUTH_USER_MODEL, verbose_name='Owner')),
            ],
            options={
                'verbose_name': 'Device group',
                'verbose_name_plural': 'Device groups',
                'ordering': ('user_id', 'name'),
                'unique_together': {('user', 'name')},
            },
        ),
        migrations.AddField(
            model_name='rustdeskpeer',
            name='machine_group',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='peers', to='api.machinegroup', verbose_name='Device group'),
        ),
    ]
