import factory
from factory.django import DjangoModelFactory
from django.contrib.auth.models import User
from core.models import Actor, Note, Activity, PortabilityOutbox


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f'user_{n}')
    email = factory.LazyAttribute(lambda o: f'{o.username}@example.com')
    password = factory.PostGenerationMethodCall('set_password', 'testpass123')
    is_staff = False
    is_active = True

class ActorFactory(DjangoModelFactory):
    class Meta:
        model = Actor

    user = factory.SubFactory(UserFactory)
    username = factory.SelfAttribute('user.username')
    full_name = factory.Faker('name')
    previously = factory.Dict({})

    """
    Check if username failes any validation:
        1. Contains non-alphanumeric characters
        2. Contains spaces
        3. Is less than 3 characters
    """
    @factory.post_generation
    def validate_username(self, create, extracted, **kwargs):
        if not self.username.isalnum() or ' ' in self.username or len(self.username) < 3:
            # Remove non-alphanumeric characters
            self.username = ''.join(c for c in self.username if c.isalnum())
            # If resulting username is too short, 
            if len(self.username) < 3:
                self.username += 'x' * (3 - len(self.username))
            self.save()

class NoteFactory(DjangoModelFactory):
    class Meta:
        model = Note

    actor = factory.SubFactory(ActorFactory)
    content = factory.Faker('text', max_nb_chars=200)
    visibility = factory.Iterator(['public', 'private', 'followers-only'])

class ActivityFactory(DjangoModelFactory):
    class Meta:
        model = Activity

    actor = factory.SubFactory(ActorFactory)
    type = factory.Iterator(['Create', 'Like', 'Update', 'Follow', 'Announce', 'Delete', 'Undo', 'Flag'])
    note = factory.SubFactory(NoteFactory)
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
            self.activities.add(ActivityFactory(actor=self.actor))
