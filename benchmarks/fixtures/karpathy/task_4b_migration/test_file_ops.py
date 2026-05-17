import os
import tempfile

from file_ops import build_path, exists, parent_of, name_of


def test_build_path():
    p = build_path("a", "b", "c.txt")
    assert p == os.path.join("a", "b", "c.txt")


def test_exists_and_name_of():
    with tempfile.NamedTemporaryFile() as tf:
        assert exists(tf.name)
        assert name_of(tf.name) == os.path.basename(tf.name)


def test_parent_of():
    assert parent_of(os.path.join("x", "y", "z.txt")) == os.path.join("x", "y")
