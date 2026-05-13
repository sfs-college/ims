"""
Migration: Add MasterInventoryAccess model and fix Room.incharge to allow null.

- Room.incharge: CASCADE → SET_NULL, null=True, blank=True
  (Fixes PeopleDeleteView which sets room.incharge = None before saving)
- MasterInventoryAccess: new model tracking view + edit access grants
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0012_roombooking_add_return_note'),
        ('core', '0003_rename_udpated_on_department_updated_on'),
    ]

    operations = [
        # Fix Room.incharge: allow null so PeopleDeleteView can set it to None
        migrations.AlterField(
            model_name='room',
            name='incharge',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='rooms_incharge',
                to='core.userprofile',
            ),
        ),
        # Add MasterInventoryAccess model
        migrations.CreateModel(
            name='MasterInventoryAccess',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('can_view', models.BooleanField(default=True, help_text='Allow view-only access to master inventory')),
                ('can_edit', models.BooleanField(default=False, help_text='Allow inline editing of master inventory items')),
                ('granted_on', models.DateTimeField(auto_now_add=True)),
                ('updated_on', models.DateTimeField(auto_now=True)),
                ('granted_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='master_inventory_grants',
                    to='core.userprofile',
                )),
                ('incharge', models.OneToOneField(
                    limit_choices_to={'is_incharge': True},
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='master_inventory_access',
                    to='core.userprofile',
                )),
                ('organisation', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='core.organisation',
                )),
            ],
            options={
                'verbose_name': 'Master Inventory Access',
                'verbose_name_plural': 'Master Inventory Accesses',
            },
        ),
    ]
