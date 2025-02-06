import random
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from testbed.core.factories import (
    ActorFactory,
    CreateActivityFactory,
    LikeActivityFactory,
    FollowActivityFactory,
    NoteFactory
)


class Command(BaseCommand):
    help = 'Seed the database with sample data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--no-prompt',
            action='store_true',
            help='Automatically create admin user without prompting'
        )

    def handle(self, *args, **kwargs):
        try:
            # Check for admin user
            if not User.objects.filter(is_staff=True, is_active=True).exists():
                if kwargs['no_prompt']:
                    self.stdout.wriute(self.style.WARNING('Creating admin user automatically...'))
                    User.objects.create_superuser(
                        username='admin',
                        email='admin@testing.com',
                        password='admin123'
                    )
                    self.stdout.write(self.style.SUCCESS('Admin user created successfully.'))
                else:
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

            # Track created likes
            like_count = 0

            # Create notes and various activities
            self.stdout.write('Creating notes and activities...')
            for actor in actors:
                # Create some notes
                notes = NoteFactory.create_batch(3, actor=actor)

                # Create activities for each note
                for note in notes:
                    create_activity = CreateActivityFactory(
                        actor=actor,
                        note=note,
                        visibility='public'
                    )
                    actor.portability_outbox.first().add_activity(create_activity)

                    # Some notes get liked by other actors
                    if random.choice([True, False]):
                        liker = random.choice([a for a in actors if a != actor])
                        like_activity = LikeActivityFactory(
                            actor=liker,
                            note=note,
                            visibility='public'
                        )
                        liker.portability_outbox.first().add_activity(like_activity)
                        like_count += 1

                # Create some follow relationships
                for _ in range(2): # Each actor follows 2 other actors
                    target = random.choice([a for a in actors if a != actor])
                    follow_activity = FollowActivityFactory(
                        actor=actor,
                        target_actor=target,
                        visibility='public'
                    )
                    actor.portability_outbox.first().add_activity(follow_activity)

            # Count all activities
            total_actors = len(actors)
            total_notes = len(actors) * 3
            total_creates = total_notes + total_actors # Notes + Actor creates
            total_follows = len(actors) * 2

            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully created:\n'
                    f'- {total_actors} actors\n'
                    f'- {total_notes} notes\n'
                    f'- {total_creates} Create activities ({total_actors} for actors, {total_notes} for notes)\n'
                    f'- {like_count} Like activities\n'
                    f'- {total_follows} Follow activities'
                )
            )

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error seeding database: {str(e)}'))
