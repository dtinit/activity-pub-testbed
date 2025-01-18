from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from testbed.core.models import Actor, PortabilityOutbox, Activity, Note
from faker import Faker
from datetime import datetime, date, timedelta


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
            else:
                self.stdout.write(self.style.WARNING('Skipping admin user creation.'))
        else:
            self.stdout.write(self.style.SUCCESS('Admin user already exists.'))

        # Create multiple tests actors and associated data
        for _ in range(10):
            # Creating User
            username = fake.user_name()
            email = fake.email()
            user, created = User.objects.get_or_create(
                username=username,
                defaults={'email': email}
            )
            if created:
                self.stdout.write(f'Created user: {username}')
            
            # Creating Actor
            full_name = fake.name()
            last_day_last_year = datetime(date.today().year, 1, 1) - timedelta(days=1)
            created_at = fake.date_time_between(start_date='-2y', end_date=last_day_last_year)            
            updated_at = fake.date_time_this_year()
            previously = {} # TODO: Check how to generate data for this field
            actor, created = Actor.objects.get_or_create(
                user=user,
                username=username,
                defaults={
                    'full_name': full_name,
                    'created_at': created_at,
                    'updated_at': updated_at,
                    'previously': previously
                }
            )

            if created:
                self.stdout.write(f'Created actor: {actor}')

            # Create Notes and Activities
            # Each note is linked to an activity
            notes = []
            activities = []

            for _ in range(5):
                note = Note.objects.create(
                    actor=actor,
                    content=fake.text(),
                    published=datetime.now(),
                    visibility='public' # We could change this to random.choices
                )
                self.stdout.write(f'Created note for actor: {username}')
                notes.append(note)

                activity = Activity.objects.create(
                    actor=actor,
                    type='Create', # Could be fake.random_element(elements=('Create', 'Like', 'Update', 'Follow', 'Announce', 'Delete', 'Undo', 'Flag')),
                    note=note,
                    timestamp=datetime.now(),
                    visibility='public' # We could change this to random.choices
                )
                self.stdout.write(f'Created activity for actor: {username}')
                activities.append(activity)

            # Create PortabilityOutbox
            # Each outbox is linked to an actor
            """
            outbox, created = PortabilityOutbox.objects.get_or_create(actor=actor)
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created outbox for actor: {username}'))
            # outbox.notes.set(notes)
            outbox.activities.set(activities)
            """

            outbox, created = PortabilityOutbox.objects.get_or_create(actor=actor)

            if created:
                self.stdout.write(self.style.SUCCESS(f'Created outbox for actor: {username}'))
            
            # Add activities one by one
            for activity in activities:
                outbox.activities.add(activity)
                self.stdout.write(self.style.SUCCESS(f'Added activity {activity.id} to outbox for actor: {username}'))

        self.stdout.write(self.style.SUCCESS('Database seeding completed.'))
    