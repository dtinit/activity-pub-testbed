from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Actor, Note, Activity, PortabilityOutbox
from .mixins import JSONLDSerializerMixin


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'password')

    def create(self, validated_data):
        return User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password']
        )

class ActorSerializer(JSONLDSerializerMixin, serializers.ModelSerializer):
    json_ld = serializers.SerializerMethodField()  # Explicitly declare the field

    class Meta:
        model = Actor
        fields = ["id", "json_ld"]


class NoteSerializer(JSONLDSerializerMixin, serializers.ModelSerializer):
    json_ld = serializers.SerializerMethodField()

    class Meta:
        model = Note
        fields = ["id", "json_ld"]


class ActivitySerializer(JSONLDSerializerMixin, serializers.ModelSerializer):
    json_ld = serializers.SerializerMethodField()

    class Meta:
        model = Activity
        fields = ["id", "json_ld"]


class PortabilityOutboxSerializer(JSONLDSerializerMixin, serializers.ModelSerializer):
    json_ld = serializers.SerializerMethodField()

    class Meta:
        model = PortabilityOutbox
        fields = ["id", "actor", "json_ld"]
