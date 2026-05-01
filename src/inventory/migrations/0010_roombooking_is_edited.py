from django.db import migrations, models


class Migration(migrations.Migration):
    """
    The 'is_edited' column already exists in the production database
    (added directly via SQL) but was missing from the Django model.
    We use SeparateDatabaseAndState so Django records the migration as
    applied without trying to ADD the column again (which would fail with
    DuplicateColumn). The state operation keeps Django's migration graph
    in sync with the model.
    """

    dependencies = [
        ('inventory', '0009_alter_roombooking_requirements_doc_and_more'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            # Django updates its internal state to know the field exists
            state_operations=[
                migrations.AddField(
                    model_name='roombooking',
                    name='is_edited',
                    field=models.BooleanField(
                        default=False,
                        help_text='True if this booking was edited after initial creation.'
                    ),
                ),
            ],
            # No actual SQL is run — column already exists in the DB
            database_operations=[],
        ),
    ]
