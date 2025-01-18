from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from testbed.core.models import Actor, PortabilityOutbox, Activity, Note
from faker import Faker

class Command(BaseCommand):
    help = 'Seed the database with testing data'

    def handle(self, *args, **kwargs):
        fake = Faker()

        """
            Check for admin user.
            Just for testing purposes.
            It won't be allowed in production.
        """
        if not User.objects.filter(is_staff=True, is_active=True).exists():
            self.stdout.write(self.style.WARNING('No admin user found.'))
            answer = input('Would you like to create one? (Y/N): ').strip().lower()
            if answer == 'y':
                self.stdout.write(self.style.WARNING('Creating admin user...'))
                User.objects.create_superuser(
                    username='admin',
                    email='admin@testing.com',
                    # password='admin123'
                )
            

