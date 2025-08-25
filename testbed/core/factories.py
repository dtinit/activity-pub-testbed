import factory
from factory.django import DjangoModelFactory
from django.contrib.auth.models import User
from datetime import datetime, timezone, timedelta
from oauth2_provider.models import Application, AccessToken
from testbed.core.models import (
    Actor,
    Note,
    CreateActivity,
    LikeActivity,
    FollowActivity,
    PortabilityOutbox,
    Following,
    Followers,
)

# Base factory for creating Users without associated actors
class UserOnlyFactory(DjangoModelFactory):
    class Meta:
        model = User
        skip_postgeneration_save = True

    username = factory.Sequence(lambda n: f"user_{n}")
    email = factory.LazyAttribute(lambda o: f"{o.username}@example.com")
    password = factory.PostGenerationMethodCall("set_password", "testpass123")
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    is_staff = False
    is_active = True

# Factory for creating Users with associated actors
class UserWithActorsFactory(UserOnlyFactory):
    @factory.post_generation
    def actors(self, create, extracted, **kwargs):
        if not create:
            return
        
        # Just save the user - signal will handle actor creation
        self.save()

class ActorFactory(DjangoModelFactory):
    class Meta:
        model = Actor
        skip_postgeneration_save = True  # Prevents duplicate initialization

    user = factory.SubFactory(UserOnlyFactory)
    username = factory.LazyAttribute(lambda o: f"{o.user.username}_{o.role}")
    role = factory.Iterator([Actor.ROLE_SOURCE, Actor.ROLE_DESTINATION])
    previously = factory.List([])

class NoteFactory(DjangoModelFactory):
    class Meta:
        model = Note

    actor = factory.SubFactory(ActorFactory)
    content = factory.Faker("text", max_nb_chars=200)
    visibility = factory.Iterator(["public", "private", "followers-only"])

class CreateActivityFactory(DjangoModelFactory):
    # Can create activities for notes or actor creation announcements
    class Meta:
        model = CreateActivity

    actor = factory.SubFactory(ActorFactory)
    note = factory.SubFactory(NoteFactory)
    visibility = factory.Iterator(["public", "private", "followers-only"])

class LikeActivityFactory(DjangoModelFactory):
    class Meta:
        model = LikeActivity

    actor = factory.SubFactory(ActorFactory)
    visibility = factory.Iterator(["public", "private", "followers-only"])
    
    # By default create a local like
    note = factory.SubFactory(NoteFactory)
    object_url = None
    object_data = None

    class Params:
        remote = factory.Trait(
            note=None,
            object_url=factory.Sequence(lambda n: f"https://remote.example/notes/{n}"),
            object_data=factory.Dict({
                'content': factory.Faker('text', max_nb_chars=50),
                'type': 'Note'
            })
        )

        
class FollowActivityFactory(DjangoModelFactory):
    class Meta:
        model = FollowActivity

    actor = factory.SubFactory(ActorFactory)
    visibility = factory.Iterator(["public", "private", "followers-only"])
    
    # By default create a local follow
    target_actor = factory.SubFactory(ActorFactory)
    target_actor_url = None
    target_actor_data = None

    class Params:
        remote = factory.Trait(
            target_actor=None,
            target_actor_url=factory.Sequence(lambda n: f"https://remote.example/users/user_{n}"),
            target_actor_data=factory.Dict({
                'preferredUsername': factory.Faker('user_name'),
                'type': 'Person'
            })
        )

class PortabilityOutboxFactory(DjangoModelFactory):
    class Meta:
        model = PortabilityOutbox

    actor = factory.SubFactory(ActorFactory)

    @factory.post_generation
    def activities(self, create, extracted, **kwargs):
        # Adds activities to the outbox after creation
        if not create:
            return

        if extracted:
            for activity in extracted:
                self.add_activity(activity)
        else:
            # By default, add a Create activity for the Actor
            activity = CreateActivityFactory(
                actor=self.actor,
                note=None,
                visibility="public"
            )
            self.add_activity(activity)


# Factory for Following relationship model (current state, not historical activities)
class FollowingFactory(DjangoModelFactory):
    class Meta:
        model = Following

    actor = factory.SubFactory(ActorFactory)
    target_actor = factory.SubFactory(ActorFactory)
    status = Following.STATUS_ACTIVE
    
    # For local relationships, leave remote fields empty
    target_actor_url = None
    target_actor_data = None

    class Params:
        # Trait for remote following relationships
        remote = factory.Trait(
            target_actor=None,
            target_actor_url=factory.Sequence(lambda n: f"https://remote.example/users/user_{n}"),
            target_actor_data=factory.Dict({
                'preferredUsername': factory.Faker('user_name'),
                'name': factory.Faker('name'),
                'type': 'Person'
            })
        )
        
        # Trait for inactive relationships
        inactive = factory.Trait(
            status=Following.STATUS_INACTIVE
        )

# Factory for Followers relationship model (current state, not historical activities)
class FollowersFactory(DjangoModelFactory):
    class Meta:
        model = Followers

    actor = factory.SubFactory(ActorFactory)
    follower_actor = factory.SubFactory(ActorFactory)
    status = Followers.STATUS_ACTIVE
    
    # For local relationships, leave remote fields empty
    follower_actor_url = None
    follower_actor_data = None

    class Params:
        # Trait for remote follower relationships
        remote = factory.Trait(
            follower_actor=None,
            follower_actor_url=factory.Sequence(lambda n: f"https://remote.example/users/follower_{n}"),
            follower_actor_data=factory.Dict({
                'preferredUsername': factory.Faker('user_name'),
                'name': factory.Faker('name'),
                'type': 'Person'
            })
        )
        
        # Trait for inactive relationships
        inactive = factory.Trait(
            status=Followers.STATUS_INACTIVE
        )

# OAuth-related factories for testing authentication
class ApplicationFactory(DjangoModelFactory):
    class Meta:
        model = Application
    
    name = factory.Sequence(lambda n: f"Test Application {n}")
    client_type = Application.CLIENT_CONFIDENTIAL
    authorization_grant_type = Application.GRANT_AUTHORIZATION_CODE
    redirect_uris = "http://localhost:8000/callback/"

class AccessTokenFactory(DjangoModelFactory):
    class Meta:
        model = AccessToken
    
    user = factory.SubFactory(UserOnlyFactory)
    application = factory.SubFactory(ApplicationFactory)
    token = factory.Sequence(lambda n: f"test-token-{n}")
    scope = "read write"
    expires = factory.LazyFunction(lambda: datetime.now(timezone.utc) + timedelta(hours=1))
    
    class Params:
        lola_scope = factory.Trait(
            scope='activitypub_account_portability read write'
        )
        expired = factory.Trait(
            expires=factory.LazyFunction(lambda: datetime.now(timezone.utc) - timedelta(hours=1))
        )
