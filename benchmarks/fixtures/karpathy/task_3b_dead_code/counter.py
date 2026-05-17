class Counter:
    def __init__(self):
        self._count = 0

    def increment(self):
        self._count += 1

    def get(self):
        return self._count


# TODO: remove if unused after migration
def _old_format_count(c):
    return f"count={c}"


# TODO: remove if unused after migration
def _legacy_increment(c, n):
    return c + n
