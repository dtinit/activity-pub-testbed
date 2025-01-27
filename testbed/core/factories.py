import factory
from factory.django import DjangoModelFactory
from django.contrib.auth.models import User
from testbed.core.models import (
    Actor, Note,
    CreateActivity,
    LikeActivity,
    FollowActivity,
    PortabilityOutbox
)


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f'user_{n}')
    email = factory.LazyAttribute(lambda o: f'{o.username}@example.com')
    password = factory.PostGenerationMethodCall('set_password', 'testpass123')
    is_staff = False
    is_active = True

    @classmethod
    def _after_postgeneration(cls, instance, create, results=None):
        if create:
            instance.save()


class ActorFactory(DjangoModelFactory):
    class Meta:
        model = Actor

    user = factory.SubFactory(UserFactory)
    username = factory.SelfAttribute('user.username')
    full_name = factory.Faker('name')
    previously = factory.Dict({})


class NoteFactory(DjangoModelFactory):
    class Meta:
        model = Note

    actor = factory.SubFactory(ActorFactory)
    content = factory.Faker('text', max_nb_chars=200)
    visibility = factory.Iterator(['public', 'private', 'followers-only'])


class CreateActivityFactory(DjangoModelFactory):
    class Meta:
        model = CreateActivity

    actor = factory.SubFactory(ActorFactory)
    note = factory.SubFactory(NoteFactory)
    visibility = factory.Iterator(['public', 'private', 'followers-only'])

    # Helper method to create a CreateActivity for Actor creation
    @classmethod
    def create_for_actor(cls, actor):
        return cls.create(
            actor=actor,
            note=None, # No note means this is an Actor creation activity
            visibility='public'
        )
    

class LikeActivityFactory(DjangoModelFactory):
    class Meta:
        model = LikeActivity

    actor = factory.SubFactory(ActorFactory)
    note = factory.SubFactory(NoteFactory) # Required for Like activity
    visibility = factory.Iterator(['public', 'private', 'followers-only'])


class FollowActivityFactory(DjangoModelFactory):
    class Meta:
        model = FollowActivity

    actor = factory.SubFactory(ActorFactory)
    target_actor = factory.SubFactory(ActorFactory) # Required for Follow activity
    visibility = factory.Iterator(['public', 'private', 'followers-only'])


class PortabilityOutboxFactory(DjangoModelFactory):
    class Meta:
        model = PortabilityOutbox

    actor = factory.SubFactory(ActorFactory)

    @factory.post_generation
    def activities(self, create, extracted, **kwargs):
        if not create:
            return

        if extracted:
            for activity in extracted:
                self.activities.add(activity)

        else:
            # By default, add a Create activity for the Actor
            activity = CreateActivityFactory.create_for_actor(self.actor)
            self.activities.add(activity)
