# Generated manually — IssueRemark model

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0017_alter_itemconfiguration_id'),
    ]

    operations = [
        migrations.CreateModel(
            name='IssueRemark',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('admin_type', models.CharField(
                    choices=[('sub_admin', 'Sub Admin'), ('central_admin', 'Central Admin')],
                    max_length=20
                )),
                ('remark_text', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('issue', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='admin_remarks',
                    to='inventory.issue'
                )),
                ('created_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to='core.userprofile'
                )),
            ],
            options={
                'ordering': ['created_at'],
            },
        ),
    ]
