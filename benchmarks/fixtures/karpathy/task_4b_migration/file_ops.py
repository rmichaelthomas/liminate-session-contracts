import os


def build_path(base, *parts):
    return os.path.join(base, *parts)


def exists(path):
    return os.path.exists(path)


def parent_of(path):
    return os.path.dirname(path)


def name_of(path):
    return os.path.basename(path)
