from django.contrib import admin
from django.urls import reverse

from testbed.core.admin import NoteAdmin, PortabilityOutboxAdmin
from testbed.core.factories import TransferJobFactory
from testbed.core.models import Actor, Note, PortabilityOutbox

# Declaring `fieldsets` on NoteAdmin makes the form's field list explicit, so a column added
# to Note later would silently disappear from the admin. This catches that.
def test_note_admin_fieldsets_cover_every_editable_field():
    listed = {name for _, options in NoteAdmin.fieldsets for name in options["fields"]}
    editable = {
        field.name
        for field in Note._meta.get_fields()
        if getattr(field, "editable", False) and not field.auto_created
    }

    assert editable - listed == set(), (
        f"Note fields missing from NoteAdmin.fieldsets: {sorted(editable - listed)}"
    )

def test_superuser_can_delete_a_user_through_the_admin(admin_client, django_user_model, user_created_via_signal):
    user = user_created_via_signal
    actor_ids = list(Actor.objects.filter(user=user).values_list("pk", flat=True))
    assert PortabilityOutbox.objects.filter(actor_id__in=actor_ids).exists()

    response = admin_client.post(reverse("admin:auth_user_delete", args=[user.pk]), {"post": "yes"})

    assert response.status_code == 302
    assert not django_user_model.objects.filter(pk=user.pk).exists()
    assert not PortabilityOutbox.objects.filter(actor_id__in=actor_ids).exists()

def test_staff_cannot_delete_an_outbox(rf, django_user_model):
    request = rf.get("/")
    request.user = django_user_model(username="staff", is_staff=True)

    assert not PortabilityOutboxAdmin(PortabilityOutbox, admin.site).has_delete_permission(request)

# An edited endpoint would send users' browsers, or the client secret, wherever it points
def test_the_admin_cannot_edit_what_discovery_and_the_callback_wrote(admin_client):
    job = TransferJobFactory(
        authorization_endpoint="https://source.example/oauth/authorize/",
        token_endpoint="https://source.example/oauth/token/",
        authorized_actor_url="https://source.example/api/actors/1/",
    )
    written = {
        "authorization_endpoint": job.authorization_endpoint,
        "token_endpoint": job.token_endpoint,
        "authorized_actor_url": job.authorized_actor_url,
    }

    page = admin_client.get(reverse("admin:core_transferjob_change", args=[job.pk])).content.decode()

    assert [field for field in written if f'name="{field}"' in page] == []
    assert all(value in page for value in written.values())

# A job's OAuth state, PKCE verifier and token never reach the page, not even encrypted
def test_the_admin_never_shows_a_jobs_credentials(admin_client):
    job = TransferJobFactory(oauth_state="st4te-value-1234", pkce_verifier="ver1fier-value-5678")
    job.set_access_token("access-token-value-9012")
    job.save()
    secrets = ["st4te-value-1234", "ver1fier-value-5678", job.encrypted_access_token, "access-token-value-9012"]

    page = admin_client.get(reverse("admin:core_transferjob_change", args=[job.pk])).content.decode()

    assert job.source_base_url in page
    assert [secret for secret in secrets if secret in page] == []
