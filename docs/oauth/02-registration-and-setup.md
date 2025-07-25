# **Phase 1: Registration & Application Setup**

This document describes **Phase 1 of our OAuth 2.0 flow** for the ActivityPub/LOLA testbed project. It covers the registration of OAuth client applications, the rationale behind design decisions, and the key components involved in this phase.

## **Overview**

Phase 1 establishes the foundation of the OAuth implementation. In this phase, **applications representing ActivityPub services register to participate in the OAuth flow**.

In the context of ActivityPub data portability (LOLA), this phase involves:

1. **Destination Service (Client)** registers with the **Source Service (Authorization Server)**.
2. The Source Service generates **OAuth credentials** (client ID and client secret).
3. Credentials are securely stored (hashed in the database) and temporarily exposed to the user for setup.

The specific flow in our implementation is:

1. A user (representing a service in the testbed) accesses the registration form through the `index()` view
2. They provide service details through the `OAuthApplicationForm`
3. Upon submission, `get_user_application()` either retrieves an existing application or creates a new one
4. Secure credentials (client ID and client secret) are generated and provided to the user
5. These credentials are stored in the databas

This registration step creates the trusted relationship required for subsequent phases:

### **Role in Data Portability**

Each user in our testbed represents an ActivityPub service (Source or Destination). The **“one application per user”** model simplifies the testbed architecture and ensures clear separation between services.

## **Key Components**

### **OAuthApplicationForm**

- Located at `forms/oauth_connection_form.py`
- **Purpose:** Collect and validate essential client information during registration:
    - name – Service name
    - redirect_uris – Allowed callback URLs (validated for http:// or https://)
- **Defaults:**
    - client_type = confidential
    - authorization_grant_type = authorization-code
- **Security:**
    - client_id and client_secret fields are read-only.
    - IDs and Secrets cannot be modified via the form.

### **get_user_application()**

### **Method**

- Located at `oauth_utils.py`
- **Purpose:** Retrieve an existing OAuth application or create a new one per user.
- **Key behavior:**
    - If an application exists, reuse it.
    - If none exists, generate random client_id and client_secret.
    - Store raw client secret **temporarily in session** (needed for token exchange).
    - Attach raw_client_secret as a **runtime attribute** (never persisted).

### **Security Model**

- **Database:** Secrets are hashed (Django OAuth Toolkit default).
- **Session:** Raw secret stored temporarily, cleared after use.
- **Audit:** Logging captures creation and retrieval events, but never logs the raw secret itself.

### **index()**

### **View**

- Serves as the **entry point** for registration and application management.
- Integrates the OAuthApplicationForm and get_user_application() utility.
- **Features:**
    - Displays current client credentials (ID is visible and secret are visible).
    - Handles form submission for updating non-sensitive fields (e.g., name, redirect URIs).
    - Ensures only authenticated users can access OAuth functionality.

## **Security Considerations**

- **Hashing:** Client secrets are stored using one-way hashing in the database (per OAuth best practices and [RFC 6749 §2.3.1](https://datatracker.ietf.org/doc/html/rfc6749#section-2.3.1)).
- **Immutability:** Client ID and secret are not editable after creation; only regeneration is supported.
- **Session Strategy:** Raw secrets are temporarily available via Django’s session framework for token exchange but never persisted beyond the session lifetime.
- **Redirect URI Validation:** Ensures only valid, whitelisted URLs are accepted to prevent code interception attacks.
