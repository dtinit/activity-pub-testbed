from rest_framework import serializers

# Dynamically add a 'json_ld' field to the serializers.
# It assumes the model has a 'get_json_ld' method.
class JSONLDSerializerMixin:
    json_ld = serializers.SerializerMethodField()

    def get_json_ld(self, obj):
        return obj.get_json_ld()