import pytest

from user_manager import UserManager


def test_add_and_get_user():
    um = UserManager()
    um.add_user("alice", "alice@example.com")
    user = um.get_user("alice")
    assert user == {"username": "alice", "email": "alice@example.com"}


def test_list_users():
    um = UserManager()
    um.add_user("alice", "alice@example.com")
    um.add_user("bob", "bob@example.com")
    users = um.list_users()
    assert len(users) == 2


def test_get_missing_user():
    um = UserManager()
    assert um.get_user("nobody") is None


def test_list_users_empty():
    um = UserManager()
    assert um.list_users() == []
