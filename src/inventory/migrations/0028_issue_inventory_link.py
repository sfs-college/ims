from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0027_roombooking_alternative_slots_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='issue',
            name='inventory_item',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='reported_issues',
                to='inventory.item',
            ),
        ),
        migrations.AddField(
            model_name='issue',
            name='inventory_status',
            field=models.CharField(
                choices=[
                    ('not_linked', 'Not Linked'),
                    ('under_maintenance', 'Under Maintenance'),
                    ('active', 'Active'),
                    ('inactive', 'Inactive'),
                ],
                default='not_linked',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='issue',
            name='master_inventory_item',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='reported_issues_as_master',
                to='inventory.item',
            ),
        ),
    ]