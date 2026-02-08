from django.apps import AppConfig
from django.db import connection
from django.db.utils import OperationalError

class InventoryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'inventory'
    
    def ready(self):
        """
        Ensure EditRequest table exists.
        This is a fallback for environments where migrations fail silently.
        Runs safely once.
        """
        try:
            table_names = connection.introspection.table_names()
            if "inventory_editrequest" not in table_names:
                self._create_editrequest_table()
        except Exception:
            # Never crash app on startup
            pass

    def _create_editrequest_table(self):
        from django.db import models
        from inventory.models import EditRequest

        with connection.schema_editor() as schema_editor:
            schema_editor.create_model(EditRequest)