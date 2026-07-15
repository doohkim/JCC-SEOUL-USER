from django.core.management import BaseCommand

from config.settings._base._secrets import show_secrets


class Command(BaseCommand):
    def handle(self, *args, **options):
        show_secrets()
