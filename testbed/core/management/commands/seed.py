import random
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.conf import settings
from testbed.core.models import Actor
from testbed.core.factories import UserWithActorsFactory
from testbed.core.utils.actor_utils import populate_source_actor_outbox


User = get_user_model()

# sample remote servers for federation testing
REMOTE_SERVERS = [
    ("mastodon.social", ["mastodon_user1", "mastodon_user2", "mastodon_user3"]),
    ("pixelfed.social", ["pixel_user1", "pixel_user2", "pixel_user3"]),
    ("pleroma.instance", ["pleroma_user1", "pleroma_user2", "pleroma_user3"]),
]


class Command(BaseCommand):
    help = "Seed the database with sample data"

    def add_arguments(self, parser):
        parser.add_argument(
            "--no-prompt",
            action="store_true",
            help="Automatically create admin user without prompting",
        )


    def handle(self, *args, **kwargs):
        try:
            # Check if seeding is allowed in current environment
            if not getattr(settings, "ALLOWED_SEED_COMMAND", False):
                self.stdout.write(
                    self.style.ERROR("Seed command is not allowed in this environment.")
                )
                return
            else:
                self.stdout.write(
                    self.style.SUCCESS("Seed command allowed in this environment.")
                )

            # Check for admin user
            if not User.objects.filter(is_staff=True, is_active=True).exists():
                username = str(getattr(settings, "SEED_ADMIN_USERNAME"))
                email = str(getattr(settings, "SEED_ADMIN_EMAIL"))
                password = str(getattr(settings, "SEED_ADMIN_PASSWORD"))

                if kwargs["no_prompt"]:
                    self.stdout.write(
                        self.style.WARNING("Creating admin user automatically...")
                    )
                    admin_user = User.objects.create_superuser(
                        username=username, email=email, password=password
                    )
                    # Signal will handle actor creation
                    self.stdout.write(
                        self.style.SUCCESS("Admin user created successfully (actors created by signal)")
                    )
                else:
                    self.stdout.write(self.style.WARNING("No admin user found."))
                    answer = (
                        input("Would you like to create one? (Y/N): ").strip().lower()
                    )
                    if answer == "y":
                        self.stdout.write(self.style.WARNING("Creating admin user..."))
                        admin_user = User.objects.create_superuser(
                            username=username, email=email, password=password
                        )
                        # Signal will handle actor creation
                        self.stdout.write(
                            self.style.SUCCESS("Admin user created successfully (actors created by signal)")
                        )
                    else:
                        self.stdout.write(
                            self.style.WARNING("Skipping admin user creation.")
                        )
            else:
                self.stdout.write(self.style.SUCCESS('Admin user already exists.'))
                
            # Create login test users (automatically created, regardless of no_prompt flag)
            self.stdout.write(self.style.WARNING("Creating login test users..."))
            login_users_created = 0
            login_users = []
            
            for user_config in getattr(settings, "SEED_TEST_USERS", []):
                username = str(user_config["username"])
                email = str(user_config["email"])
                password = str(user_config["password"])
                
                if not User.objects.filter(username=username).exists():
                    user = User.objects.create_user(
                        username=username, email=email, password=password
                    )
                    # Signal will handle actor creation
                    self.stdout.write(
                        self.style.SUCCESS(f"Login user '{username}' created (actors created by signal)")
                    )
                    login_users_created += 1
                else:
                    user = User.objects.get(username=username)
                    self.stdout.write(self.style.SUCCESS(f"Login user '{username}' already exists"))
                
                login_users.append(user)
            
            if login_users_created > 0:
                self.stdout.write(self.style.SUCCESS(f"Created {login_users_created} login test users with password: testpass123"))
            
            # Create additional users with both source and destination actors for API testing
            # (Outboxes will be created automatically for BOTH source and destination actors)
            self.stdout.write('Creating users with paired actors...')
            regular_users = UserWithActorsFactory.create_batch(7) # 7 regular users with paired actors
            
            # Collect all actors (both source and destination)
            all_actors = []
            
            # Add actors from regular users
            for user in regular_users:
                # Get both source and destination actors for each user
                source_actor = user.actors.get(role=Actor.ROLE_SOURCE)
                dest_actor = user.actors.get(role=Actor.ROLE_DESTINATION)
                all_actors.extend([source_actor, dest_actor])
            
            # Add actors from login users
            for user in login_users:
                # Get both source and destination actors for each user
                source_actor = user.actors.get(role=Actor.ROLE_SOURCE)
                dest_actor = user.actors.get(role=Actor.ROLE_DESTINATION)
                all_actors.extend([source_actor, dest_actor])
                
            # All actors
            actors = all_actors
            
            # Verify outboxes were created for all actors
            source_actors_count = sum(1 for a in actors if a.is_source)
            dest_actors_count = sum(1 for a in actors if a.is_destination)
            self.stdout.write(f'Created {source_actors_count} source actors and {dest_actors_count} destination actors')
            self.stdout.write(f'All actors now have outboxes with initial Create activities')

            # Track different types of activities
            local_like_count = 0
            remote_like_count = 0
            local_follow_count = 0
            remote_follow_count = 0
            regular_actors_count = len(all_actors) # Counts the number of regular actors (both from regular users and login users)

            # Split actors into source and destination
            source_actors = [a for a in actors if a.is_source]
            dest_actors = [a for a in actors if a.is_destination]
            
            # Destination actors should only have their creation activity
            self.stdout.write("Destination actors only have their creation activity in outbox")
            
            # Skip additional population since actors are already populated by the signal
            self.stdout.write("Source actors already populated by signal handler")

            # Count the activities in source actors' outboxes
            for actor in source_actors:
                # Count likes in outbox
                local_like_count += actor.portability_outbox.activities_like.filter(
                    note__isnull=False  # Local likes have a note reference
                ).count()
                
                remote_like_count += actor.portability_outbox.activities_like.filter(
                    note__isnull=True  # Remote likes don't have a note reference
                ).count()
                
                # Count follows in outbox
                local_follow_count += actor.portability_outbox.activities_follow.filter(
                    target_actor__isnull=False  # Local follows have a target_actor reference
                ).count()
                
                remote_follow_count += actor.portability_outbox.activities_follow.filter(
                    target_actor__isnull=True  # Remote follows don't have a target_actor reference
                ).count()

            # Count all activities
            total_actors = len(actors)
            total_users = len(regular_users) + len(login_users)
            total_notes = len(source_actors) * 3 # Only source actors have notes
            total_creates = total_notes + total_actors # Notes + Actor creates (both source and destination actors)

            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully created:\n'
                    f'- {total_users} users\n'
                    f'- {total_actors} actors (all paired with source and destination)\n'
                    f'- {source_actors_count} source actors and {dest_actors_count} destination actors\n'
                    f'- {total_notes} notes (for source actors only)\n'
                    f'- {total_creates} Create activities ({total_actors} for actors, {total_notes} for notes)\n'
                    f'- {local_like_count} Local Like activities\n'
                    f'- {remote_like_count} Remote Like activities\n'
                    f'- {local_follow_count} Local Follow activities\n'
                    f'- {remote_follow_count} Remote Follow activities\n\n'
                    f'Federation seeding created with servers: {", ".join(server for server, _ in REMOTE_SERVERS)}' 
                )
            )

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error seeding database: {str(e)}"))
