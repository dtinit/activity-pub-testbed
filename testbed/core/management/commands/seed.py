from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from testbed.core.factories import ActorFactory, ActivityFactory


class Command(BaseCommand):
    help = 'Seed the database with sample data'

    def handle(self, *args, **kwargs):
        try:
            # Check for admin user
            if not User.objects.filter(is_staff=True, is_active=True).exists():
                self.stdout.write(self.style.WARNING('No admin user found.'))
                answer = input('Would you like to create one? (Y/N): ').strip().lower()
                if answer == 'y':
                    self.stdout.write(self.style.WARNING('Creating admin user...'))
                    User.objects.create_superuser(
                        username='admin',
                        email='admin@testing.com',
                        password='admin123'
                    )
                    self.stdout.write(self.style.SUCCESS('Admin user created successfully.'))
                else:
                    self.stdout.write(self.style.WARNING('Skipping admin user creation.'))
            else:
                self.stdout.write(self.style.SUCCESS('Admin user already exists.'))
            
            # Create multiple actors (Outbox will be created automatically)
            self.stdout.write('Creating actors...')
            actors = ActorFactory.create_batch(10)

            # Create activities (notes will be created automatically)
            self.stdout.write('Creating activities with their notes...')
            for actor in actors:
                ActivityFactory.create_batch(
                    5,
                    actor=actor,
                )
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully created:\n'
                    f'- {len(actors)} actors and their outboxes\n'
                    f'- {len(actors) * 5} activities with their notes'
                )
            )
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error seeding database: {str(e)}'))
