# **OAuth Implementation Overview (Authorization Code Flow)**

This document describes the **complete OAuth 2.0 Authorization Code Flow** implemented in the ActivityPub/LOLA testbed. It explains the roles of Source and Destination services, outlines the step-by-step flow, and highlights security and compliance considerations.

## **Context**

The LOLA specification ([ActivityPub Data Portability](https://swicg.github.io/activitypub-data-portability/lola.html)) defines a protocol for **live account portability** between ActivityPub servers. Our implementation enables:

- Secure data transfers initiated by the **Destination service**.
- User-controlled authorization via the **Source service** (testbed).
- Standardized export of ActivityPub data in **JSON‑LD** format.

## **Flow Overview**

### **Key Actors**

- **User** – Account owner requesting portability.
- **Destination Service (Client)** – Initiates data import.
- **Source Service (Authorization Server)** – Hosts user data and issues tokens.

## **OAuth Flow Diagram**

![OAuth Flow Diagram](../images/oauth-flow-diagram.png)

## **OAuth Flow Phases**

### **Phase 1: Registration & Application Setup**

- **Purpose:** Establish trust between services by registering clients.
- **Process:**
    1. The service requesting data (Destination) registers with the service holding the data (Source).
    2. The Source issues credentials (client ID and client secret) and stores them securely.
    3. Redirect URIs and basic metadata are set for future authorization steps.

---

### **Phase 2: Authorization Request & User Consent**

- **Purpose:** Initiate the authorization process and request user approval.
- **Process:**
    1. The Destination service directs the user to the Source with a secure request containing client details and requested permissions.
    2. The user is prompted to log in if not already authenticated.
    3. A consent screen allows the user to approve or deny access to their data.

---

### **Phase 3: Authorization Code & Callback**

- **Purpose:** Deliver a temporary code confirming user consent.
- **Process:**
    1. Upon approval, the Source generates an authorization code.
    2. The user is redirected back to the Destination with this code and a state value to confirm request integrity.
    3. The Destination prepares to exchange this code for an access token.

---

### **Phase 4: Token Exchange**

- **Purpose:** Convert the authorization code into an access token.
- **Process:**
    1. The Destination securely sends the authorization code and its credentials to the Source.
    2. The Source validates the request and returns an access token.
    3. This token will be used for accessing protected resources.

---

### **Phase 5: Protected Resource Access**

- **Purpose:** Access user data from the Source service using the access token.
- **Process:**
    1. The Destination includes the token in its requests to retrieve data (e.g., profile, posts, followers).
    2. The Source validates the token and ensures the request is within the approved scope.
    3. Data is returned in JSON-LD format aligned with ActivityPub and LOLA standards.

---

### **Phase 6: Account Recreation**

- **Purpose:** Use the retrieved data to recreate the user’s account on the new service.
- **Process:**
    1. The Destination imports the user’s exported data.
    2. The user resumes activity seamlessly on the new platform.
    3. This phase concludes the portability process.

---

## **Security Measures**

- **Authorization Code Flow** – Chosen for confidential clients (most secure option).
- **Redirect URI Validation** – Prevents open redirect vulnerabilities.
- **State Parameter** – Mitigates CSRF attacks.
- **Hashed Client Secrets** – Stored securely in DB; raw secret shown only once.
- **HTTPS Enforcement** – Required in production environments.

---

## **Error Handling & Testing Scenarios**

### **Common Error Cases**

- Invalid client_id or redirect_uri mismatch.
- Expired or invalid authorization code.
- Invalid or expired access token.
- Scope mismatch during token validation.

### **Security Tests**

- Verify state parameter prevents CSRF.
- Confirm HTTPS and redirect validation.
- Ensure rate limiting for token endpoints.

### **Data Access Validation**

- Verify returned data is JSON‑LD and LOLA-compliant.
- Ensure tokens allow only scoped access (e.g., activitypub_account_portability).

---

## **Implementation Notes**

- **One Application per User**: Simplifies testbed logic and mirrors real-world service isolation.
- **Credential Rotation**: Future enhancement — add secret regeneration endpoint for compromised clients.
- **Logging**: Record significant events (registration, authorization, token exchange) without exposing secrets.
- **Compliance**: Aligns with [RFC 6749](https://datatracker.ietf.org/doc/html/rfc6749) and LOLA portability guidelines.

---

## **Real-Case Example**

**Scenario:** A developer of “MyFediverse” registers their service and imports data:

1. Registers service at testbed → receives client_id and client_secret.
2. User at MyFediverse clicks “Import from Testbed.”
3. Redirects to testbed for login and consent.
4. Authorization code exchanged for token.
5. MyFediverse retrieves ActivityPub data (profile, posts, followers).