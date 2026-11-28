from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0028_issue_inventory_link'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='issue',
            name='inventory_item',
        ),
        migrations.RemoveField(
            model_name='issue',
            name='inventory_status',
        ),
        migrations.RemoveField(
            model_name='issue',
            name='master_inventory_item',
        ),
    ]