import factory
from factory.django import DjangoModelFactory
from django.contrib.auth.models import User
from testbed.core.models import (
    Actor,
    Note,
    CreateActivity,
    LikeActivity,
    FollowActivity,
    PortabilityOutbox,
)


class UserFactory(DjangoModelFactory):
    # Provides options to create users with or without associated actors
    class Meta:
        model = User
        skip_postgeneration_save = True  # Prevents automatic save after creation

    username = factory.Sequence(lambda n: f"user_{n}")
    email = factory.LazyAttribute(lambda o: f"{o.username}@example.com")
    password = factory.PostGenerationMethodCall("set_password", "testpass123")
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    is_staff = False
    is_active = True

    @factory.post_generation
    def with_actors(self, create, extracted, **kwargs):
        """Optional hook to create associated actors for the user
        
        Usage:
            UserFactory(with_actors=True)  # Creates user with both actors
            UserFactory(with_actors=False)  # Creates just the user
        """
        if not create:
            return
        
        self.save()
        if extracted:
            Actor.objects.create_actors_for_user(self)

# Factory for creating Actor instances
# Provides methods for creating source actors, destination actors, or pairs.
class ActorFactory(DjangoModelFactory):
    class Meta:
        model = Actor
        skip_postgeneration_save = True  # Prevents duplicate initialization

    user = factory.SubFactory(UserFactory, with_actors=False)
    username = factory.LazyAttribute(lambda o: f"{o.user.username}_{o.role}")
    role = factory.Iterator([Actor.ROLE_SOURCE, Actor.ROLE_DESTINATION])
    previously = factory.List([])

    @classmethod
    def create_source_actor(cls, **kwargs):
        return cls.create(role=Actor.ROLE_SOURCE, **kwargs)

    @classmethod
    def create_destination_actor(cls, **kwargs):
        return cls.create(role=Actor.ROLE_DESTINATION, **kwargs)

    @classmethod
    def create_pair(cls, **kwargs):
        user = UserFactory.create(with_actors=False)
        return Actor.objects.create_actors_for_user(user, **kwargs)


class NoteFactory(DjangoModelFactory):
    # Notes can only be created by source actors
    class Meta:
        model = Note

    actor = factory.SubFactory(ActorFactory, role=Actor.ROLE_SOURCE)
    content = factory.Faker("text", max_nb_chars=200)
    visibility = factory.Iterator(["public", "private", "followers-only"])


class CreateActivityFactory(DjangoModelFactory):
    # Can create activities for notes or actor creation announcements
    class Meta:
        model = CreateActivity

    actor = factory.SubFactory(ActorFactory, role=Actor.ROLE_SOURCE)
    note = factory.SubFactory(NoteFactory)
    visibility = factory.Iterator(["public", "private", "followers-only"])

    # Creates an activity announcing an actor's creation
    @classmethod
    def create_for_actor(cls, actor):
        return cls.create(
            actor=actor,
            note=None,  # No note means this is an Actor creation activity
            visibility="public",
        )


class LikeActivityFactory(DjangoModelFactory):
    # Only source actors can create like activities
    class Meta:
        model = LikeActivity

    actor = factory.SubFactory(ActorFactory, role=Actor.ROLE_SOURCE)
    note = factory.SubFactory(NoteFactory)
    visibility = factory.Iterator(["public", "private", "followers-only"])
    object_url = None
    object_data = None


class FollowActivityFactory(DjangoModelFactory):
    # Source actors follow destination actors by default
    class Meta:
        model = FollowActivity

    actor = factory.SubFactory(ActorFactory, role=Actor.ROLE_SOURCE)
    target_actor = factory.SubFactory(ActorFactory, role=Actor.ROLE_DESTINATION)
    visibility = factory.Iterator(["public", "private", "followers-only"])
    target_actor_url = None
    target_actor_data = None


class PortabilityOutboxFactory(DjangoModelFactory):
    # Only source actors have outboxes. Creates initial actor creation activity by default.
    class Meta:
        model = PortabilityOutbox

    actor = factory.SubFactory(ActorFactory, role=Actor.ROLE_SOURCE)

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
            activity = CreateActivityFactory.create_for_actor(self.actor)
            self.add_activity(activity)