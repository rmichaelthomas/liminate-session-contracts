"""benchmarks/_env.py: the bench scripts read ANTHROPIC_API_KEY from the
repo's .env, so it no longer has to be exported in the shell (where it would
also switch Claude Code off the subscription login)."""
import importlib.util
import os
import pathlib
import tempfile
import unittest
from unittest import mock

REPO = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("bench_env", REPO / "benchmarks" / "_env.py")
bench_env = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench_env)


class LoadEnvTest(unittest.TestCase):
    def write(self, text):
        handle = tempfile.NamedTemporaryFile("w", suffix=".env", delete=False)
        handle.write(text)
        handle.close()
        self.addCleanup(os.unlink, handle.name)
        return handle.name

    def test_sets_a_variable_from_the_file(self):
        path = self.write("ANTHROPIC_API_KEY=sk-test-1\n")
        with mock.patch.dict(os.environ, {}, clear=True):
            bench_env.load_env(path)
            self.assertEqual(os.environ["ANTHROPIC_API_KEY"], "sk-test-1")

    def test_the_environment_wins_over_the_file(self):
        path = self.write("ANTHROPIC_API_KEY=from-file\n")
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "from-shell"}, clear=True):
            bench_env.load_env(path)
            self.assertEqual(os.environ["ANTHROPIC_API_KEY"], "from-shell")

    def test_handles_export_prefix_quotes_comments_and_blanks(self):
        path = self.write('# key\n\nexport A="quoted value"\nB=\'single\'\nnot a pair\n')
        with mock.patch.dict(os.environ, {}, clear=True):
            bench_env.load_env(path)
            self.assertEqual(os.environ["A"], "quoted value")
            self.assertEqual(os.environ["B"], "single")
            self.assertNotIn("not a pair", os.environ)

    def test_a_missing_file_is_not_an_error(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            bench_env.load_env("/no/such/.env")
            self.assertEqual(dict(os.environ), {})

    def test_default_path_is_the_repo_root_env(self):
        self.assertEqual(bench_env.ENV_PATH, REPO / ".env")

    def test_every_bench_script_loads_it_before_creating_a_client(self):
        for script in sorted((REPO / "benchmarks").glob("bench*.py")):
            source = script.read_text(encoding="utf-8")
            if "anthropic.Anthropic(" not in source:
                continue
            with self.subTest(script=script.name):
                self.assertIn("load_env()", source)
                self.assertLess(source.index("load_env()"), source.index("anthropic.Anthropic("))

    def test_env_file_is_gitignored(self):
        import subprocess
        result = subprocess.run(["git", "check-ignore", "-q", ".env"], cwd=REPO)
        self.assertEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
