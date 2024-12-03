# Actor model

----

The Actor model represents a user or entity in the ActivityPub ecosystem. Each Actor is linked to a Django User for authentication and includes properties such as:

* **username**: A unique identifier for the Actor.
* **full_name**: The display name of the Actor.
* **previously**: A field used to store references to prior accounts, enabling account portability across servers.
This model provides a JSON-LD representation, making it interoperable with LOLA and ActivityPub-compliant systems.

## **JSON-LD Representation Example**

```json
{
  "@context": [
    "https://www.w3.org/ns/activitystreams",
    "https://swicg.github.io/activitypub-data-portability/lola.jsonld"
  ],
  "type": "Person",
  "id": "https://example.com/users/alice",
  "preferredUsername": "alice",
  "name": "Alice Example",
  "previously": {
    "type": "OrderedCollection",
    "items": [
      {
        "id": "https://oldserver.com/users/alice",
        "movedTo": "https://example.com/users/alice"
      }
    ]
  }
}
```

# Activity model

---

The Activity model represents an action performed by an Actor. These actions include creating content, liking, following, and other ActivityPub-defined types. Key properties include:

* **type**: The type of activity (e.g., Create, Like).
* **note**: A link to a Note if the activity involves creating or interacting with content.
* **visibility**: Defines who can see the activity (public, private, etc.).

This model ensures compatibility with ActivityStreams and generates JSON-LD for each activity.

## **JSON-LD Representation Example**

```json
{
  "@context": "https://www.w3.org/ns/activitystreams",
  "type": "Create",
  "id": "https://example.com/activities/1",
  "actor": "https://example.com/users/alice",
  "published": "2024-11-08T12:00:00Z",
  "visibility": "public",
  "object": {
    "@context": "https://www.w3.org/ns/activitystreams",
    "type": "Note",
    "id": "https://example.com/notes/1",
    "attributedTo": "https://example.com/users/alice",
    "content": "Hello, world!",
    "published": "2024-11-08T12:00:00Z",
    "visibility": "public"
  }
}
```

# Note model

---

The Note model represents textual content authored by an Actor. It includes:

* **content**: The main text of the note.
* **linked_to**: A reference to the Actor who created the note.
* **visibility**: Controls the audience for the note (public, private, etc.).

Notes are a core content type in ActivityPub and can be linked to activities like Create or Announce.

# PortabilityOutbox Model

---

The PortabilityOutbox model aggregates all activities performed by an Actor, providing a collection for account portability. Key features include:

* A many-to-many relationship with Activity, allowing the outbox to collect multiple actions.
* A JSON-LD representation of the outbox, structured as an OrderedCollection.

This model plays a central role in exporting account data in a LOLA-compliant format.

## **JSON-LD Representation Example**

```json
{
  "@context": "https://www.w3.org/ns/activitystreams",
  "type": "OrderedCollection",
  "id": "https://example.com/users/alice/outbox",
  "totalItems": 1,
  "items": [
    {
      "@context": "https://www.w3.org/ns/activitystreams",
      "type": "Create",
      "id": "https://example.com/activities/1",
      "actor": "https://example.com/users/alice",
      "published": "2024-11-08T12:00:00Z",
      "visibility": "public",
      "object": {
        "@context": "https://www.w3.org/ns/activitystreams",
        "type": "Note",
        "id": "https://example.com/notes/1",
        "attributedTo": "https://example.com/users/alice",
        "content": "Hello, world!",
        "published": "2024-11-08T12:00:00Z",
        "visibility": "public"
      }
    }
  ]
}
```