from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0010_roombooking_is_edited'),
    ]

    operations = [
        migrations.AddField(
            model_name='issue',
            name='incharge_remark',
            field=models.TextField(
                blank=True,
                null=True,
                help_text='Progress update from room incharge sent to the reporter.'
            ),
        ),
    ]
