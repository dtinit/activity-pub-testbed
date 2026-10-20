# Source Server Guide (Mode A)

The ActivityPub Account Portability Testbed implements [LOLA v0.3](https://swicg.github.io/activitypub-data-portability/lola.html),
the account portability specification for [ActivityPub](https://www.w3.org/TR/activitypub/), as a **source** server. Sign up, and your account comes with posts, likes, follows, followers and blocks to
migrate; then point your destination at it. This guide covers what your destination has to do, and the ways
to check each step.

## Ways to test

All of them use the same setup and the same flow, so you can mix them. For example, run the Postman
collection first to see a working exchange, then point your own code at the same account.

| Method | Good for | You need |
|---|---|---|
| **Your own destination** | The real test: your implementation against a compliant source | Your code, an HTTPS callback |
| **The Postman collection** (`mode-a.postman_collection.json`) | Seeing every request and response, with each step checked for you | [Postman](https://www.postman.com/downloads/) |
| **newman** | Re-running the same collection from a terminal or CI | Node.js and `npm install -g newman` (run with 6.2.3) |
| **curl, or any HTTP client** | Walking the protocol by hand | A terminal |

## Setup

1. **Sign up** at <https://ap-testbed.dtinit.org/account/signup/> with an address you can receive mail at:
   the testbed sends a confirmation email. For a second account, an alias such as `you+b@example.com` works.
   The dashboard shows two actors: **Source** (`<name>_source`, the account you migrate) and Destination
2. **Find your Actor URL**: the Source card's **Details** link, `https://ap-testbed.dtinit.org/api/actors/<id>/`.
   This is what a user would give your destination
3. **Copy your client credentials** from **Update Your OAuth Connection**: Client ID and Client Secret. Every
   account has its own OAuth client, created for you
4. **Register your callback** in **Redirect URL** (several URLs are separated by spaces), then **Update**.
   It must use `https://`. For the collection or curl, use `https://localhost:9999/callback`. Nothing needs to
   listen there: after you approve, the browser fails to connect and the authorization response is in its
   address bar, so the code never leaves your machine

## The flow: what your destination does

Each step shows the request as `curl`. Replace `<…>`; `$ACTOR` is your Actor URL.

### 1 · Discover the endpoints

Fetch the Actor anonymously and read `endpoints.oauthMigrationEndpoint` (LOLA §5, MUST; `endpoints` is the
Actor property from [ActivityPub §4.1](https://www.w3.org/TR/activitypub/#actor-objects)). Then fetch the
[RFC 8414](https://www.rfc-editor.org/rfc/rfc8414) metadata at the Actor's origin for the `token_endpoint`.

```bash
curl -s -H "Accept: application/activity+json" "$ACTOR" | jq .endpoints
curl -s https://ap-testbed.dtinit.org/.well-known/oauth-authorization-server | jq
```

The metadata's `authorization_endpoint` and `activitypub_account_portability` both equal the Actor's
`oauthMigrationEndpoint`; `scopes_supported` lists `activitypub_account_portability`.

### 2 · Send the user to authorize

Redirect the user's browser to the authorization endpoint ([RFC 6749 §4.1](https://www.rfc-editor.org/rfc/rfc6749#section-4.1)) with:

| Parameter | Value |
|---|---|
| `response_type` | `code` |
| `client_id` | your Client ID |
| `redirect_uri` | the callback you registered, exactly |
| `scope` | `activitypub_account_portability` |
| `state` | a random value you keep, to check in step 3 |
| `code_challenge`, `code_challenge_method` | optional [PKCE](https://www.rfc-editor.org/rfc/rfc7636) (`S256`); if you send them, send `code_verifier` in step 4 |

```
https://ap-testbed.dtinit.org/oauth/authorize/?response_type=code&client_id=<client id>&redirect_uri=https%3A%2F%2Flocalhost%3A9999%2Fcallback&scope=activitypub_account_portability&state=<random>
```

A signed-out user signs in (or signs up) first and comes straight back. The consent screen names the
account being granted (`Account`, `Actor ID` and `Scope`), with **Authorize Data Transfer** and **Cancel**.

### 3 · Handle the callback

On approval the browser arrives at your callback with three parameters (LOLA §5.3):

```
https://localhost:9999/callback?code=<code>&state=<state>&activitypub_actor=https%3A%2F%2Fap-testbed.dtinit.org%2Fapi%2Factors%2F<id>%2F
```

- **Check `state`** is the value you sent, and stop if it is not
- **Use `activitypub_actor`** as the account to migrate. LOLA: the destination *"MUST use the Actor ID
  provided with the authorization code rather than the original one the user communicated"*
- On **Cancel**, the callback gets `error=access_denied` instead

### 4 · Exchange the code for a token

`POST` the token endpoint with your client credentials as HTTP Basic ([RFC 6749 §2.3.1](https://www.rfc-editor.org/rfc/rfc6749#section-2.3.1)). The code is single-use and expires
after **10 minutes**.

```bash
curl -s -u "<client id>:<client secret>" \
  -d grant_type=authorization_code -d "code=<code>" \
  -d "redirect_uri=https://localhost:9999/callback" \
  https://ap-testbed.dtinit.org/oauth/token/
```

The response holds `access_token`, `token_type: Bearer`, `expires_in: 3600` and
`scope: activitypub_account_portability`. A `refresh_token` is issued too.

### 5 · Read the account

Send `Authorization: Bearer <token>` ([RFC 6750](https://www.rfc-editor.org/rfc/rfc6750)) and `Accept: application/activity+json` on every request, starting from
`activitypub_actor`:

```bash
curl -s -H "Authorization: Bearer <token>" -H "Accept: application/activity+json" "<activitypub_actor>" | jq '{migration, liked, followers}'
```

With the token, the Actor carries a `migration` object with exactly `outbox`, `content`, `following` and
`blocked`, plus the `liked`, `followers` and `blocked` collections. Without it, none of these appear. Then
fetch each URL as given:

| Collection | What it holds |
|---|---|
| `migration.outbox` | The `Create` activities of the account's Notes, every visibility |
| `migration.content` | The same Notes, without activity wrappers |
| `migration.following` | The accounts this account follows |
| `migration.blocked` | The accounts it blocks ([FEP-c648](https://codeberg.org/fediverse/fep/src/branch/main/fep/c648/fep-c648.md)) |
| `liked` | The objects of its Likes, every visibility |
| `followers` | Its followers. Readable with the token, but a destination does not copy them (LOLA §6.6) |

What your code can rely on:

- **One envelope.** Every collection is an [`OrderedCollection`](https://www.w3.org/TR/activitystreams-vocabulary/#dfn-orderedcollection) with `id`, `totalItems` and `orderedItems`
  (never `items`), newest first, in **one page**. There is no pagination yet
- **Use URLs exactly as given.** Every ID ends in `/`; without the slash a URL answers `301`.
- **The token is bound to one account.** Anything belonging to another account answers `403 actor_mismatch`,
  even when it is public. So do not dereference an embedded actor's `id` with the migration token; embedded
  actors already carry `name` and `inbox`
- **Content types.** Responses are `application/activity+json` ([ActivityPub §3.2](https://www.w3.org/TR/activitypub/#retrieving-objects)). `Accept: application/ld+json;
  profile="https://www.w3.org/ns/activitystreams"` also works; plain `application/ld+json` and `text/html`
  answer `406`

### Errors

LOLA errors are JSON with `error_code`, `detail` and `endpoint`, and carry `Access-Control-Allow-Origin: *`:

| Status | `error_code` / `error` | When |
|---|---|---|
| `403` | `insufficient_scope` | No token (or an invalid one) on a collection that needs the portability scope |
| `403` | `actor_mismatch` | A token used on another account's Actor, collection or object |
| `404` | `object_not_found` | A missing object, or a non-public one that is not yours |
| `406` | | An `Accept` header the API cannot serve |
| `400` | `invalid_grant` | At the token endpoint: a spent, expired or unknown code |
| `401` | `invalid_client` | At the token endpoint: a wrong client ID or secret |

## Using the Postman collection

Import `mode-a.postman_collection.json` and `mode-a.postman_environment.json`. In the environment, fill in
`actor_url`, `client_id` and `client_secret` and keep them **local**: in Postman 12 the environment has one
**Value** column, and a ☁ icon marks a value shared with your workspace. (Older versions have two columns;
use **Current value**, which stays on your machine.) Keep `redirect_uri` as `https://localhost:9999/callback`,
and select the environment in the top-right selector.

The folders follow the flow above, with checks on every response:

| Folder | Checks |
|---|---|
| 1 · Discovery | `oauthMigrationEndpoint`, the metadata, the public outbox |
| 2 · Authorize | Makes `state` and a PKCE challenge, checks the signed-out redirect, prints the authorize URL |
| 3 · Token | `state` and `activitypub_actor` before spending the code, then the exchange |
| 4 · Read the account | The scoped Actor, every collection non-empty with the shared envelope |
| 5 · What is refused | Anonymous and invalid tokens, another account, a spent code, a wrong secret, `text/html` |

Send the requests one by one, reading each response's **Test Results** tab, or use the Runner with **Keep
variable values** on. Either way the run has one hand-off, so run folders 1 and 2 first:

1. Send **2.1**. It answers `302`, and then prints an authorize URL in the **Console** (bottom left). The same
   URL is saved in the environment as `authorize_url`
2. Open it in a browser, sign in, check that the consent screen names your account, and approve
3. Copy the whole address-bar URL into `callback_url`, save the environment, and run folders 3, 4 and 5
   within 10 minutes. Sending 2.1 again makes a new `state`, so start again from step 1 if you do

**Cross-account checks** (5.4 to 5.7) need a second account and are skipped without one. After a run as the
first account, request 4.9 prints `other_actor_url` and `other_private_note_url`; set both in the environment.
Then do what a real second user does: send 2.1 again, open the URL in a signed-out browser window, and sign up
(or sign in) as the second account from the sign-in page. The consent screen names that account, and the
callback's `activitypub_actor` is its Actor. Run folders 3, 4 and 5: the collection follows `activitypub_actor`
(LOLA §5.3; request 3.1 logs that it differs from the discovered Actor), reads the second account, and checks
that its token is refused on the first account's resources.

Good to know:

- The first request after a quiet period can take about 15 seconds while the server starts; send one before
  a demo
- Several wrong passwords in a row lock sign-in for that account for a few minutes

**With newman**, the same collection runs in two steps, passing state through an exported environment.
Exporting the environment from Postman leaves out local values, so fill in `actor_url`, `client_id` and
`client_secret` in the file itself:

```bash
newman run docs/source-server/testing/mode-a.postman_collection.json -e ~/mode-a.postman_environment.json \
  --folder "1 · Discovery" --folder "2 · Authorize" --export-environment /tmp/mode-a-run.json

# approve in the browser, then:
newman run docs/source-server/testing/mode-a.postman_collection.json -e /tmp/mode-a-run.json \
  --env-var "callback_url=<the address bar>" \
  --folder "3 · Token" --folder "4 · Read the account" --folder "5 · What is refused"

rm /tmp/mode-a-run.json   # it holds your client secret and token
```

## What you should see

A new account always gets the same content, so the counts are fixed:

| Collection | `totalItems` |
|---|---|
| Outbox, anonymous / with the token | 19 / 43 |
| `migration.outbox` | 30 |
| `migration.content`, Notes spread over about four months | 30 |
| `migration.following` | 6 |
| `migration.blocked` | 2 |
| `liked` | 6 |
| `followers` | 8 |

The remote accounts in these collections use reserved `.example` domains, so a destination that acts on them
(for example, re-following) reaches no real server.

## Testing a local copy

Run `python manage.py runserver` and use `http://localhost:8000/api/actors/<id>/` as the Actor URL. Use
`localhost`, not `127.0.0.1`: the local metadata names `http://localhost:8000`, and request 1.2 fails if the
Actor's origin differs. A local copy also accepts `http://` callbacks.

## Keep your credentials private

Never commit your client secret or a filled-in environment file. Tokens last one hour.

## References

- [LOLA Portability for ActivityPub, v0.3](https://swicg.github.io/activitypub-data-portability/lola.html): §5 discovery and authorization, §6 the migration collections
- [ActivityPub](https://www.w3.org/TR/activitypub/) (W3C Recommendation): Actor objects, collections, retrieving objects
- [Activity Streams 2.0 Core](https://www.w3.org/TR/activitystreams-core/) and [Activity Streams 2.0 Vocabulary](https://www.w3.org/TR/activitystreams-vocabulary/): the object model, `OrderedCollection`, `Create`, `Note`
- [RFC 6749](https://www.rfc-editor.org/rfc/rfc6749): OAuth 2.0, the authorization code grant
- [RFC 6750](https://www.rfc-editor.org/rfc/rfc6750): Bearer token usage
- [RFC 7636](https://www.rfc-editor.org/rfc/rfc7636): PKCE
- [RFC 8414](https://www.rfc-editor.org/rfc/rfc8414): OAuth 2.0 authorization server metadata
- [FEP-c648](https://codeberg.org/fediverse/fep/src/branch/main/fep/c648/fep-c648.md): the Blocked collection
