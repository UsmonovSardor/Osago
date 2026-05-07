from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = "Create default admin"

    def handle(self, *args, **kwargs):
        phone = "998901234567"
        password = "Admin123!"

        if not User.objects.filter(phone=phone).exists():
            User.objects.create_superuser(phone=phone, password=password)
            self.stdout.write(self.style.SUCCESS(f"Admin created: {phone}"))
        else:
            self.stdout.write(self.style.WARNING("Admin already exists"))
