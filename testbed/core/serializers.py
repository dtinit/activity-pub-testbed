from rest_framework import serializers
from .models import Actor, Note, Activity, PortabilityOutbox
from .mixins import JSONLDSerializerMixin

class ActorSerializer(JSONLDSerializerMixin, serializers.ModelSerializer):
    json_ld = serializers.SerializerMethodField() # Explicitly declare the field

    class Meta:
        model = Actor
        fields = ['id', 'json_ld']


class NoteSerializer(JSONLDSerializerMixin, serializers.ModelSerializer):
    json_ld = serializers.SerializerMethodField()

    class Meta:
        model = Note
        fields = ['id', 'json_ld']


class ActivitySerializer(JSONLDSerializerMixin, serializers.ModelSerializer):
    json_ld = serializers.SerializerMethodField()

    class Meta:
        model = Activity
        fields = ['id', 'json_ld']


class PortabilityOutboxSerializer(JSONLDSerializerMixin, serializers.ModelSerializer):
    actor = serializers.StringRelatedField()  # Actor reference
    activities = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    json_ld = serializers.SerializerMethodField()

    class Meta:
        model = PortabilityOutbox
        fields = ['id', 'actor', 'activities', 'json_ld']
