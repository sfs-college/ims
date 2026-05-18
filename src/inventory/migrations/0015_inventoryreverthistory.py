from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_rename_udpated_on_department_updated_on'),
        ('inventory', '0014_assigninventoryaccess'),
    ]

    operations = [
        migrations.CreateModel(
            name='InventoryRevertHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('item_name', models.CharField(max_length=255)),
                ('category_name', models.CharField(blank=True, default='', max_length=255)),
                ('brand_name', models.CharField(blank=True, default='', max_length=255)),
                ('quantity', models.PositiveIntegerField()),
                ('room_total_before', models.PositiveIntegerField(default=0)),
                ('room_total_after', models.PositiveIntegerField(default=0)),
                ('master_total_after', models.PositiveIntegerField(default=0)),
                ('note', models.CharField(blank=True, default='', max_length=255)),
                ('reverted_on', models.DateTimeField(auto_now_add=True)),
                ('organisation', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.organisation')),
                ('reverted_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='inventory_reverts', to='core.userprofile')),
                ('room', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='inventory.room')),
            ],
            options={
                'ordering': ['-reverted_on'],
            },
        ),
    ]
