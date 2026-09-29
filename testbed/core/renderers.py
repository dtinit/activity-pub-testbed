"""
DRF renderers for the two media types ActivityPub serves its JSON under.

ActivityPub §3.2: servers "MUST present an ActivityStreams object representation in response to
application/ld+json; profile="https://www.w3.org/ns/activitystreams", and SHOULD also present the
ActivityStreams representation in response to application/activity+json as well." With only DRF's
default renderers, both of those Accept headers get a 406.
"""

from rest_framework.renderers import JSONRenderer


class ActivityJSONRenderer(JSONRenderer):
    media_type = "application/activity+json"


class ActivityStreamsJSONLDRenderer(JSONRenderer):
    media_type = 'application/ld+json; profile="https://www.w3.org/ns/activitystreams"'
