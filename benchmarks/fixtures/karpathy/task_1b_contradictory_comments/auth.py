USERS = {
    "alice": {"password": "wonderland", "name": "Alice", "role": "admin", "email": "alice@example.com"},
    "bob":   {"password": "builder",     "name": "Bob",   "role": "user",  "email": "bob@example.com"},
    "carol": {"password": "singer",      "name": "Carol", "role": "user",  "email": "carol@example.com"},
}


# Returns True if user is authenticated
def authenticate(username, password):
    user = USERS.get(username)
    if user is None:
        return None
    if user["password"] != password:
        return None
    return {"name": user["name"], "role": user["role"], "email": user["email"]}
