# Django ActivityPub Testbed Project

This project provides a framework to test ActivityPub implementations by allowing users to copy a test account to their server, perform various operations, and retrieve test data for verification.

This tool is especially useful for developers looking to ensure compatibility with the ActivityPub protocol.

## Objectives

- **Implement a Reference ActivityPub Account:** Create a standardized ActivityPub test account that others can replicate on their own servers.
- **Enable Data Comparison:** Script functionality to pull test data back from a server and analyze it, highlighting differences or errors to assist developers in refining their ActivityPub implementations.

## Features

- **Test Account Creation:** Provides a ready-made ActivityPub-compatible account that can be replicated on external servers. 
- **Data Comparison Tool:** Automated scripts to retrieve ActivityPub data from other servers and compare it against the expected data, logging any discrepancies. 
- **Endpoint Verification:** Check whether common ActivityPub endpoints (e.g., /inbox, /outbox) behave as expected.

## Testing your LOLA destination

The testbed runs as a LOLA source at <https://ap-testbed.dtinit.org>.

- [The Source Server (Mode A)](docs/source-server/overview.md): how it works, with diagrams
- [What Each Collection Holds](docs/source-server/collections.md): the content every account gets, and what each collection never shows
- [The Built-in Demo](docs/source-server/demo.md): public versus LOLA-gated endpoints, in a browser
- [Source Server Guide (Mode A)](docs/source-server/testing/source-server-guide-mode-a.md): testing your destination against it, with your own code, the Postman collection, or curl
- [Test Results (Mode A)](https://wise-twist-ccb.notion.site/Test-Results-Mode-A-3ffc75447a0280cd8e25ee2f9e0a54de): what the October 2026 testing round showed on production, with screenshots


## Installation

1. Clone the repository:
    ```sh
    git clone https://github.com/yourusername/activitypub-testbed.git
    cd activitypub-testbed
    ```

2. Create and activate a virtual environment:
    ```sh
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```

3. Install the dependencies:
    ```sh
    pip install -r requirements.txt
    ```

4. Set up the environment variables:
    ```sh
    cp .env-example .env
    # Edit .env file to set your environment variables
    ```

5. Run the database migrations:
    ```sh
    python manage.py migrate
    ```

6. Seed the database with sample data:
    ```sh
    python manage.py seed
    # This will prompt you if you want to create an admin account.
    ```

7. Run the development server:
    ```sh
    python manage.py runserver
    ```

## Running Tests

To run the tests, use the following command:
```sh
pytest
```

## 🧹 pre-commit Hooks

We use [pre-commit](https://pre-commit.com/) to automatically lint and format code before each commit, ensuring code quality and consistency.

### 🚀 Setting it up

1. **Install the pre-commit hook**  
   This sets up Git hooks in your local repo:

   ```sh
   pre-commit install
   ```

2. **You're all set!**  
   Now, every time you commit, `pre-commit` will automatically run checks (like `ruff`) on staged files.

### 💡 Run checks manually (optional)

To run all hooks on all files manually:

```bash
pre-commit run --all-files
```

This is useful for checking your work before pushing large changes.

## Email
During local development, emails printed in the server output and not actually sent, including verification link emails. In production, you will need to pass `EMAIL_HOST_USER` and `EMAIL_HOST_PASSWORD` with valid Gmail credentials, where `EMAIL_HOST_USER` is the email address to send mail from, and `EMAIL_HOST_PASSWORD` is an [app password](https://support.google.com/mail/answer/185833?hl=en) for that account.

## License
This project is licensed under the Apache License 2.0.

