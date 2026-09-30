from django.contrib import admin
from django.urls import reverse

from testbed.core.admin import NoteAdmin, PortabilityOutboxAdmin
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
