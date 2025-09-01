import random
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.conf import settings
from testbed.core.models import Actor, Following, Followers
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

    def generate_social_relationships(self, source_actors):
        """
        Generate realistic social relationships for LOLA collections testing.
        
        Creates varied popularity patterns with both local and remote relationships
        to simulate real-world ActivityPub social networks.
        
        Args:
            source_actors: List of source Actor objects
            
        Returns:
            tuple: (following_count, followers_count, remote_relationships_count)
        """
        following_count = 0
        followers_count = 0
        remote_relationships_count = 0
        
        if len(source_actors) < 2:
            self.stdout.write(self.style.WARNING("Not enough actors for social relationships"))
            return 0, 0, 0
        
        # Create personas with different popularity levels
        actors_list = list(source_actors)
        
        # Assign persona types for realistic social patterns
        popular_actors = actors_list[:2] if len(actors_list) >= 2 else []  # Popular influencers
        casual_actors = actors_list[2:6] if len(actors_list) >= 6 else actors_list[2:]  # Regular users
        newcomer_actors = actors_list[6:] if len(actors_list) > 6 else []  # New users
        
        # Generate local following relationships with realistic patterns
        for actor in actors_list:
            # Determine how many accounts this actor follows based on persona
            if actor in popular_actors:
                follow_count = random.randint(8, 15)  # Popular users follow many
            elif actor in casual_actors:
                follow_count = random.randint(3, 8)   # Casual users follow some
            else:  # newcomer
                follow_count = random.randint(1, 4)   # New users follow few
            
            # Select random actors to follow (excluding self)
            potential_targets = [a for a in actors_list if a != actor]
            targets = random.sample(potential_targets, min(follow_count, len(potential_targets)))
            
            for target in targets:
                # Create Following relationship
                following, created = Following.objects.get_or_create(
                    actor=actor,
                    target_actor=target,
                    defaults={'status': Following.STATUS_ACTIVE}
                )
                if created:
                    following_count += 1
                    
                    # Create corresponding Follow activity in outbox for consistency
                    from testbed.core.factories import FollowActivityFactory
                    follow_activity = FollowActivityFactory(
                        actor=actor,
                        target_actor=target,
                        visibility="public"
                    )
                    actor.portability_outbox.add_activity(follow_activity)
                
                # Create corresponding Followers relationship
                follower, created = Followers.objects.get_or_create(
                    actor=target,
                    follower_actor=actor,
                    defaults={'status': Followers.STATUS_ACTIVE}
                )
                if created:
                    followers_count += 1
        
        # Generate remote relationships for federation testing
        for i, actor in enumerate(actors_list[:5]):  # First 5 actors get remote relationships
            # Create 1-2 remote following relationships per actor
            remote_follow_count = random.randint(1, 2)
            
            for _ in range(remote_follow_count):
                # Select random remote server and user
                server, usernames = random.choice(REMOTE_SERVERS)
                username = random.choice(usernames)
                
                # Create remote actor data
                remote_actor_url = f"https://{server}/users/{username}"
                remote_actor_data = {
                    "type": "Person",
                    "id": remote_actor_url,
                    "preferredUsername": username,
                    "name": f"{username.replace('_', ' ').title()}",
                    "summary": f"ActivityPub user from {server}",
                    "inbox": f"https://{server}/users/{username}/inbox",
                    "outbox": f"https://{server}/users/{username}/outbox",
                    "followers": f"https://{server}/users/{username}/followers",
                    "following": f"https://{server}/users/{username}/following"
                }
                
                # Create remote Following relationship
                following, created = Following.objects.get_or_create(
                    actor=actor,
                    target_actor_url=remote_actor_url,
                    defaults={
                        'target_actor_data': remote_actor_data,
                        'status': Following.STATUS_ACTIVE
                    }
                )
                if created:
                    following_count += 1
                    remote_relationships_count += 1
                    
                    # Create corresponding remote Follow activity in outbox for consistency
                    from testbed.core.factories import FollowActivityFactory
                    remote_follow_activity = FollowActivityFactory.create(
                        remote=True,  # Uses remote trait
                        actor=actor,
                        target_actor_url=remote_actor_url,
                        target_actor_data=remote_actor_data,
                        visibility="public"
                    )
                    actor.portability_outbox.add_activity(remote_follow_activity)
        
        # Create some remote followers for popular actors (federation incoming)
        for actor in popular_actors:
            # Popular actors get 1-3 remote followers
            remote_follower_count = random.randint(1, 3)
            
            for _ in range(remote_follower_count):
                # Select random remote server and user
                server, usernames = random.choice(REMOTE_SERVERS)
                username = random.choice(usernames)
                
                # Ensure unique remote follower
                remote_follower_url = f"https://{server}/users/{username}_follower_{_}"
                
                # Create remote follower data
                remote_follower_data = {
                    "type": "Person", 
                    "id": remote_follower_url,
                    "preferredUsername": f"{username}_follower_{_}",
                    "name": f"Remote Follower {username.replace('_', ' ').title()}",
                    "summary": f"Remote follower from {server}",
                    "inbox": f"https://{server}/users/{username}_follower_{_}/inbox",
                    "outbox": f"https://{server}/users/{username}_follower_{_}/outbox"
                }
                
                # Create remote Followers relationship
                follower, created = Followers.objects.get_or_create(
                    actor=actor,
                    follower_actor_url=remote_follower_url,
                    defaults={
                        'follower_actor_data': remote_follower_data,
                        'status': Followers.STATUS_ACTIVE
                    }
                )
                if created:
                    followers_count += 1
                    remote_relationships_count += 1
        
        return following_count, followers_count, remote_relationships_count


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

            # Generate realistic social relationships for LOLA collections
            # This ensures consistency between outbox Follow activities and Following collection state
            self.stdout.write(self.style.WARNING("Generating realistic social relationships..."))
            following_count, followers_count, remote_relationships_count = self.generate_social_relationships(source_actors)
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Social graph generated:\n'
                    f'- {following_count} Following relationships\n'
                    f'- {followers_count} Followers relationships\n'
                    f'- {remote_relationships_count} Remote actor relationships\n'
                )
            )

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
