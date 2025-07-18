# Generated by Django 5.1.3 on 2025-05-25 20:42

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Actor',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('username', models.CharField(max_length=100, unique=True)),
                ('role', models.CharField(choices=[('source', 'Source Service'), ('destination', 'Destination Service')], max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('previously', models.JSONField(blank=True, default=list, null=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='actors', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='FollowActivity',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('visibility', models.CharField(choices=[('public', 'Public'), ('private', 'Private'), ('followers-only', 'Followers only')], default='public', max_length=20)),
                ('target_actor_url', models.URLField(blank=True, help_text='URL of the followed actor in the fediverse', null=True)),
                ('target_actor_data', models.JSONField(blank=True, help_text='Metadata of the followed actor', null=True)),
                ('actor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(class)s_activities', to='core.actor')),
                ('target_actor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='follow_activities_received', to='core.actor')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Note',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content', models.TextField()),
                ('published', models.DateTimeField(auto_now_add=True)),
                ('visibility', models.CharField(choices=[('public', 'Public'), ('private', 'Private'), ('followers-only', 'Followers Only')], default='public', max_length=20)),
                ('actor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notes', to='core.actor')),
            ],
        ),
        migrations.CreateModel(
            name='LikeActivity',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('visibility', models.CharField(choices=[('public', 'Public'), ('private', 'Private'), ('followers-only', 'Followers only')], default='public', max_length=20)),
                ('object_url', models.URLField(blank=True, help_text='URL of the liked object in the fediverse', null=True)),
                ('object_data', models.JSONField(blank=True, help_text='Metadata of the liked object', null=True)),
                ('actor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(class)s_activities', to='core.actor')),
                ('note', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='like_activities', to='core.note')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='CreateActivity',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('visibility', models.CharField(choices=[('public', 'Public'), ('private', 'Private'), ('followers-only', 'Followers only')], default='public', max_length=20)),
                ('actor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(class)s_activities', to='core.actor')),
                ('note', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='create_activities', to='core.note')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='PortabilityOutbox',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('activities_create', models.ManyToManyField(related_name='outboxes', to='core.createactivity')),
                ('activities_follow', models.ManyToManyField(related_name='outboxes', to='core.followactivity')),
                ('activities_like', models.ManyToManyField(related_name='outboxes', to='core.likeactivity')),
                ('actor', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='portability_outbox', to='core.actor')),
            ],
            options={
                'constraints': [models.UniqueConstraint(fields=('actor',), name='unique_actor_outbox')],
            },
        ),
    ]
