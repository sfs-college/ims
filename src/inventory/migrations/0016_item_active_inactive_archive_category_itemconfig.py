from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0015_inventoryreverthistory'),
    ]

    operations = [
        # Add active_count and inactive_count to Item
        migrations.AddField(
            model_name='item',
            name='active_count',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='item',
            name='inactive_count',
            field=models.IntegerField(default=0),
        ),
        # Add serviceable_count and unserviceable_count to Item
        migrations.AddField(
            model_name='item',
            name='serviceable_count',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='item',
            name='unserviceable_count',
            field=models.IntegerField(default=0),
        ),
        # Update Archive model: add archive_category, archive_status, updated_on; make remark optional
        migrations.AddField(
            model_name='archive',
            name='archive_category',
            field=models.CharField(
                choices=[('serviceable', 'Serviceable'), ('unserviceable', 'Unserviceable')],
                default='serviceable',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='archive',
            name='archive_status',
            field=models.CharField(
                choices=[
                    ('archived', 'Archived'),
                    ('under_maintenance', 'Under Maintenance'),
                    ('serviced', 'Serviced'),
                    ('not_serviceable', 'Not Serviceable'),
                ],
                default='archived',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='archive',
            name='updated_on',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AlterField(
            model_name='archive',
            name='archive_type',
            field=models.CharField(
                blank=True,
                choices=[('consumption', 'Consumption'), ('depreciation', 'Depreciation')],
                default='consumption',
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name='archive',
            name='remark',
            field=models.TextField(blank=True, default=''),
        ),
        # Create ItemConfiguration model
        migrations.CreateModel(
            name='ItemConfiguration',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('configuration_name', models.CharField(blank=True, default='', max_length=255)),
                ('configuration_data', models.TextField(default='[]', help_text='JSON array of {spec, value} objects')),
                ('count', models.PositiveIntegerField(default=1, help_text='How many of this item have this configuration')),
                ('created_on', models.DateTimeField(auto_now_add=True)),
                ('updated_on', models.DateTimeField(auto_now=True)),
                ('slug', models.SlugField(max_length=255, unique=True)),
                ('organisation', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.organisation')),
                ('room', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='inventory.room')),
                ('item', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='configurations', to='inventory.item')),
                ('created_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='item_configurations_created',
                    to='core.userprofile',
                )),
            ],
        ),
    ]
