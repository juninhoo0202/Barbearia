from django.apps import AppConfig
import os

class BarbeariaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'barbearia'

    def ready(self):
        import barbearia.signals
        if os.environ.get("RUN_MAIN") == "true":
            from barbearia.scheduler import scheduler
            if not scheduler.running:
                scheduler.start()
