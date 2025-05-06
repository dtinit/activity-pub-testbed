from django.core.exceptions import ValidationError

def validate_username(value):
    if " " in value or not value.isalnum():
        raise ValidationError("Username must be alphanumeric and contain no spaces.")
    if len(value) < 3:
        raise ValidationError("Username must be at least 3 characters.")