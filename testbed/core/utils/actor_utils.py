import random
from datetime import timedelta
from django.utils import timezone
from testbed.core.models import Actor, LikeActivity, FollowActivity
from testbed.core.factories import NoteFactory, CreateActivityFactory, LikeActivityFactory, FollowActivityFactory
import logging

logger = logging.getLogger(__name__)

# Sample remote servers for federation testing (same as in seed.py)
REMOTE_SERVERS = [
    ("mastodon.social", ["mastodon_user1", "mastodon_user2", "mastodon_user3"]),
    ("pixelfed.social", ["pixel_user1", "pixel_user2", "pixel_user3"]),
    ("pleroma.instance", ["pleroma_user1", "pleroma_user2", "pleroma_user3"]),
]

def create_remote_like(actor):
    # Create a like activity for a remote object""
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
            "published": (
                timezone.now() - timedelta(days=random.randint(1, 30))
            ).isoformat(),
            "visibility": "public",
        },
        visibility="public",
    )

def create_remote_follow(actor):
    # Create a follow activity for a remote actor
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

def populate_source_actor_outbox(source_actor, num_notes=3, include_local_interactions=True):
    """
    Populate a source actor's outbox with sample content
    
    Args:
        source_actor: The source actor to populate the outbox for
        num_notes: Number of notes to create
        include_local_interactions: Whether to include interactions with local actors
    
    Returns:
        A dictionary with counts of created objects
    """
    result = {
        "notes": 0,
        "local_likes": 0,
        "remote_likes": 0,
        "local_follows": 0,
        "remote_follows": 0,
    }
    
    try:
        # Create local notes
        notes = NoteFactory.create_batch(num_notes, actor=source_actor)
        result["notes"] = len(notes)

        # Create activities for each note
        for note in notes:
            create_activity = CreateActivityFactory(
                actor=source_actor, note=note, visibility="public"
            )
            source_actor.portability_outbox.add_activity(create_activity)

            # Some notes get liked by other source actors (local likes)
            if include_local_interactions and random.choice([True, False]):
                # Find another source actor to be the liker
                other_actors = Actor.objects.filter(
                    role=Actor.ROLE_SOURCE
                ).exclude(id=source_actor.id)
                
                if other_actors.exists():
                    liker = random.choice(list(other_actors))
                    like_activity = LikeActivityFactory(
                        actor=liker, note=note, visibility="public"
                    )
                    liker.portability_outbox.add_activity(like_activity)
                    result["local_likes"] += 1

        # Create remote likes
        num_remote_likes = random.randint(1, 3)
        for _ in range(num_remote_likes):
            remote_like = create_remote_like(source_actor)
            source_actor.portability_outbox.add_activity(remote_like)
            result["remote_likes"] += 1

        # Create local follows if possible
        if include_local_interactions:
            other_actors = Actor.objects.exclude(id=source_actor.id)
            if other_actors.exists():
                target = random.choice(list(other_actors))
                follow_activity = FollowActivityFactory(
                    actor=source_actor, target_actor=target, visibility="public"
                )
                source_actor.portability_outbox.add_activity(follow_activity)
                result["local_follows"] += 1

        # Create remote follows
        remote_follow = create_remote_follow(source_actor)
        source_actor.portability_outbox.add_activity(remote_follow)
        result["remote_follows"] += 1
        
        logger.info(f"Populated outbox for {source_actor.username} with: " + 
                   f"{result['notes']} notes, {result['local_likes']} local likes, " +
                   f"{result['remote_likes']} remote likes, {result['local_follows']} local follows, " +
                   f"{result['remote_follows']} remote follows")
        
    except Exception as e:
        logger.error(f"Error populating outbox for {source_actor.username}: {e}")
    
    return result
