from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0019_issueremark_inventory_i_issue_i_021bc0_idx'),
    ]

    operations = [
        migrations.AddField(
            model_name='item',
            name='is_serviceable',
            field=models.BooleanField(default=True),
        ),
    ]
