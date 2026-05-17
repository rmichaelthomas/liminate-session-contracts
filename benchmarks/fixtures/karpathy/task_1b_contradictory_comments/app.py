from auth import authenticate


def greet(username, password):
    user = authenticate(username, password)
    if not user:
        return "access denied"
    return f"hello {user['name']} ({user['role']})"


def send_welcome_email(username, password):
    user = authenticate(username, password)
    if not user:
        return False
    print(f"sending welcome to {user['email']} for {user['name']}")
    return True


def is_admin(username, password):
    user = authenticate(username, password)
    return bool(user) and user["role"] == "admin"
