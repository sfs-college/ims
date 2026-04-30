from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0007_roombookingrequest_recommended_by_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='roombooking',
            name='status',
            field=models.CharField(
                choices=[('active', 'Active'), ('completed', 'Completed'), ('cancelled', 'Cancelled')],
                default='active',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='roombooking',
            name='cancelled_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='cancelled_bookings',
                to='core.userprofile',
            ),
        ),
        migrations.AddField(
            model_name='roombooking',
            name='cancelled_on',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
