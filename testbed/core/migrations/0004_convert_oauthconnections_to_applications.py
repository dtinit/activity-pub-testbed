# Generated by Django 5.1.3 on 2025-06-27 22:11

from django.db import migrations


def convert_oauth_connections_to_applications(apps, schema_editor):

    OauthConnection = apps.get_model('core', 'OauthConnection')
    Application = apps.get_model('oauth2_provider', 'Application')
    
    for conn in OauthConnection.objects.all():
        Application.objects.create(
            user=conn.user,
            name=f"{conn.user.username}'s OAuth App",
            client_id=conn.client_id,
            client_secret=conn.client_secret,
            redirect_uris=conn.redirect_url,
            client_type='confidential',
            authorization_grant_type='authorization-code',
            skip_authorization=False
        )
        print(f"Migrated OAuth connection for user: {conn.user.username}")


def reverse_migration(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_add_outbox_to_destination_actors'),
        ('oauth2_provider', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(
            convert_oauth_connections_to_applications,
            reverse_migration
        ),
    ]
