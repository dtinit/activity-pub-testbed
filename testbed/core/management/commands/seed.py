import random
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.conf import settings
from django.utils import timezone
from testbed.core.models import LikeActivity, FollowActivity
from testbed.core.factories import (
    ActorFactory,
    CreateActivityFactory,
    LikeActivityFactory,
    FollowActivityFactory,
    NoteFactory
)


User = get_user_model()

# sample remote servers for federation testing
REMOTE_SERVERS = [
    ("mastodon.social", ["mastodon_user1", "mastodon_user2", "mastodon_user3"]),
    ("pixelfed.social", ["pixel_user1", "pixel_user2", "pixel_user3"]),
    ("pleroma.instance", ["pleroma_user1", "pleroma_user2", "pleroma_user3"]),
]

class Command(BaseCommand):
    help = 'Seed the database with sample data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--no-prompt',
            action='store_true',
            help='Automatically create admin user without prompting'
        )

    # Create a series of remote likes
    def create_remote_like(self, actor):
        server, usernames = random.choice(REMOTE_SERVERS)
        username = random.choice(usernames)
        note_id = random.randint(1000, 9999)

        return LikeActivity.objects.create(
            actor=actor,
            note=None,
            object_url=f"https://{server}/notes/{note_id}",
            object_data={
                "@context": "https://www.w3.org/ns/activitystreams",
                "type": "Note",
                "actor": f"https://{server}/users/{username}",
                "content": f"A federated note from {username} on {server}",
                "published": (timezone.now() - timedelta(days=random.randint(1, 30))).isoformat(),
                "visibility": "public",
            },
            visibility="public"
        )

    def create_remote_follow(self, actor):
        server, usernames = random.choice(REMOTE_SERVERS)
        username = random.choice(usernames)

        return FollowActivity.objects.create(
            actor=actor,
            target_actor=None,
            target_actor_url=f"https://{server}/users/{username}",
            target_actor_data={
                "type": "Person",
                "preferredUsername": username,
                "name": username,
                "url": f"https://{server}/users/{username}",
            },
            visibility="public"
        )

    def handle(self, *args, **kwargs):
        try:

            # Check if seeding is allowed in current environment
            if not getattr(settings, 'ALLOWED_SEED_COMMAND', False):
                self.stdout.write(
                    self.style.ERROR('Seed command is not allowed in this environment.')
                )
                return
            else:
                self.stdout.write(self.style.SUCCESS('Seed command allowed in this environment.'))


            # Check for admin user
            if not User.objects.filter(is_staff=True, is_active=True).exists():
                username = str(getattr(settings, 'SEED_ADMIN_USERNAME'))
                email = str(getattr(settings, 'SEED_ADMIN_EMAIL'))
                password = str(getattr(settings, 'SEED_ADMIN_PASSWORD'))

                if kwargs['no_prompt']:
                    self.stdout.write(self.style.WARNING('Creating admin user automatically...'))
                    User.objects.create_superuser(
                        username=username,
                        email=email,
                        password=password
                    )
                    self.stdout.write(self.style.SUCCESS('Admin user created successfully.'))
                else:
                    self.stdout.write(self.style.WARNING('No admin user found.'))
                    answer = input('Would you like to create one? (Y/N): ').strip().lower()
                    if answer == 'y':
                        self.stdout.write(self.style.WARNING('Creating admin user...'))
                        User.objects.create_superuser(
                            username=username,
                            email=email,
                            password=password
                        )
                        self.stdout.write(self.style.SUCCESS('Admin user created successfully.'))
                    else:
                        self.stdout.write(self.style.WARNING('Skipping admin user creation.'))
            else:
                self.stdout.write(self.style.SUCCESS('Admin user already exists.'))
            
            # Create multiple actors (Outbox will be created automatically)
            self.stdout.write('Creating actors...')
            actors = ActorFactory.create_batch(10)

            # Track different types of activities
            local_like_count = 0
            remote_like_count = 0
            local_follow_count = 0
            remote_follow_count = 0

            # Create notes and various activities
            self.stdout.write('Creating notes and activities...')
            for actor in actors:
                # Create local notes
                notes = NoteFactory.create_batch(3, actor=actor)

                # Create activities for each note
                for note in notes:
                    create_activity = CreateActivityFactory(
                        actor=actor,
                        note=note,
                        visibility='public'
                    )
                    actor.portability_outbox.first().add_activity(create_activity)

                    # Some notes get liked by other actors (local likes)
                    if random.choice([True, False]):
                        liker = random.choice([a for a in actors if a != actor])
                        like_activity = LikeActivityFactory(
                            actor=liker,
                            note=note,
                            visibility='public'
                        )
                        liker.portability_outbox.first().add_activity(like_activity)
                        local_like_count += 1

                # Create remote likes for each actor
                for _ in range(random.randint(1, 3)):
                    remote_like = self.create_remote_like(actor)
                    actor.portability_outbox.first().add_activity(remote_like)
                    remote_like_count += 1

                # Create local follows
                for _ in range(1): # Each actor follows 1 local actor
                    target = random.choice([a for a in actors if a != actor])
                    follow_activity = FollowActivityFactory(
                        actor=actor,
                        target_actor=target,
                        visibility='public'
                    )
                    actor.portability_outbox.first().add_activity(follow_activity)
                    local_follow_count += 1

                # Create remote follows
                for _ in range(1): # Each actor follows 1 remote actor
                    remote_follow = self.create_remote_follow(actor)
                    actor.portability_outbox.first().add_activity(remote_follow)
                    remote_follow_count += 1

            # Count all activities
            total_actors = len(actors)
            total_notes = len(actors) * 3
            total_creates = total_notes + total_actors # Notes + Actor creates

            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully created:\n'
                    f'- {total_actors} actors\n'
                    f'- {total_notes} notes\n'
                    f'- {total_creates} Create activities ({total_actors} for actors, {total_notes} for notes)\n'
                    f'- {local_like_count} Local Like activities\n'
                    f'- {remote_like_count} Remote Like activities\n'
                    f'- {local_follow_count} Local Follow activities\n'
                    f'- {remote_follow_count} Remote Follow activities\n\n'
                    f'Federation seeding created with servers: {", ".join(server for server, _ in REMOTE_SERVERS)}' 
                )
            )

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error seeding database: {str(e)}'))
            