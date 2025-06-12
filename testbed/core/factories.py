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
        
        self.save()
        Actor.objects.create_actors_for_user(self)

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