from testbed.core.admin import NoteAdmin
from testbed.core.models import Note

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
