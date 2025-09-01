import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_followers_following'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='OAuthClientCredentials',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('encrypted_client_secret', models.TextField(help_text='Client secret encrypted with Fernet using Django SECRET_KEY')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='oauth_credentials', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'OAuth Client Credentials',
                'verbose_name_plural': 'OAuth Client Credentials',
            },
        ),
    ]
