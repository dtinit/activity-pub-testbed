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

## License
This project is licensed under the Apache License 2.0.