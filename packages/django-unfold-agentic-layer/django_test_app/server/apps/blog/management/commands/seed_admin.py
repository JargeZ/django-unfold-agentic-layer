from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create the demo superuser admin/admin if it doesn't exist (local demo only)."

    def handle(self, *args, **options):
        User = get_user_model()
        if User.objects.filter(username="admin").exists():
            self.stdout.write("Superuser 'admin' already exists.")
            return
        User.objects.create_superuser("admin", "admin@example.com", "admin")
        self.stdout.write(self.style.SUCCESS("Created superuser admin/admin."))
