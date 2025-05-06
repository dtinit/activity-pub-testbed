from django.contrib.auth.models import AbstractUser
from django.db import models

class TesterUser(AbstractUser):
    """
    Custom user model for testers who will test the LOLA implementation.
    These users are completely separate from Actors and are used for authentication
    and OAuth testing.
    """
    email = models.EmailField('email address', unique=True)
    is_tester = models.BooleanField(default=True)
    email_verified = models.BooleanField(default=False)

    USERNAME_FIELD = 'email' # Use email for authentication instead of username
    REQUIRED_FIELDS = [] # Email is always required bu USERNAME_FIELD

    class Meta:
        verbose_name = "tester"
        verbose_name_plural = "testers"
    
    def __str__(self):
        return self.email