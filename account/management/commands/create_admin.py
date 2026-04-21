from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model


class Command(BaseCommand):
    help = "Create superuser automatically"

    def handle(self, *args, **kwargs):
        User = get_user_model()

        email = "admin@gmail.com"
        password = "admin123"
        full_name = "Admin User"

        try:
            # 🔥 FIX: use email instead of username
            if not User.objects.filter(email=email).exists():
                User.objects.create_superuser(
                    email=email,
                    password=password,
                    full_name=full_name
                )
                self.stdout.write(self.style.SUCCESS("Superuser created"))
            else:
                self.stdout.write("Superuser already exists")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {e}"))