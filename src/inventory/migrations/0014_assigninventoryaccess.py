from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0013_add_master_inventory_access_and_fix_room_incharge'),
        ('core', '0003_rename_udpated_on_department_updated_on'),
    ]

    operations = [
        migrations.CreateModel(
            name='AssignInventoryAccess',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('can_assign', models.BooleanField(default=True, help_text='Allow incharge to assign master inventory to their rooms')),
                ('granted_on', models.DateTimeField(auto_now_add=True)),
                ('updated_on', models.DateTimeField(auto_now=True)),
                ('granted_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='assign_inventory_grants',
                    to='core.userprofile',
                )),
                ('incharge', models.OneToOneField(
                    limit_choices_to={'is_incharge': True},
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='assign_inventory_access',
                    to='core.userprofile',
                )),
                ('organisation', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='core.organisation',
                )),
            ],
            options={
                'verbose_name': 'Assign Inventory Access',
                'verbose_name_plural': 'Assign Inventory Accesses',
            },
        ),
    ]
