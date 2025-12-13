from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0021_alter_item_available_count'),
    ]

    operations = [
        migrations.RenameField(
            model_name='item',
            old_name='achived_count',
            new_name='archived_count',
        ),
    ]
