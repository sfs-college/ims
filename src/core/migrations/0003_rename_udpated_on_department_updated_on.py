# Fix typo: rename udpated_on → updated_on in Department model

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_alter_department_department_name'),
    ]

    operations = [
        migrations.RenameField(
            model_name='department',
            old_name='udpated_on',
            new_name='updated_on',
        ),
    ]
