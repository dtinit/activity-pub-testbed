from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
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
    
class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        user = authenticate(username=data['username'], password=data['password'])
        if not user:
            raise serializers.ValidationError('Invalid username or password.')
        
        if not user.is_active:
            raise serializers.ValidationError('User account is disabled.')
        
        # Add user to validated data for view to use
        data['user'] = user
        return data

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
