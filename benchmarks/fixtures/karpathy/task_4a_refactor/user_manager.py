class Database:
    """In-memory stub standing in for a real DB connection."""
    def __init__(self):
        self._rows = {}

    def insert(self, key, value):
        self._rows[key] = value

    def get(self, key):
        return self._rows.get(key)

    def all(self):
        return list(self._rows.values())


class UserManager:
    def __init__(self):
        self.db = Database()

    def add_user(self, username, email):
        self.db.insert(username, {"username": username, "email": email})

    def get_user(self, username):
        return self.db.get(username)

    def list_users(self):
        return self.db.all()
