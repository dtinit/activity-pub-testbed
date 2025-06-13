import string
import secrets

def random_client_id(length=10):
    return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(length))

def random_client_secret(length=40):
    return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(length))