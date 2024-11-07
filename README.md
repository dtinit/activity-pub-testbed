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
