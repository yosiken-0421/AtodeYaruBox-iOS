"""CI fixture lifecycle regressions. Xcode/Simulator are mocked."""
from contextlib import contextmanager, redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import sys
import unittest
from unittest.mock import patch
import uuid

PREPARED = Path(__file__).resolve().parents[2] / "artifacts"
ACTIVE_TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PREPARED.parent / "tools"))
spec = importlib.util.spec_from_file_location("build_prepared", ACTIVE_TOOLS / "build_mac.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ExternalQABuildTests(unittest.TestCase):
    def setUp(self):
        self.root = PREPARED / ("external-build-host-test-" + uuid.uuid4().hex)
        self.root.mkdir()
        self.artifacts = self.root / "artifacts"
        self.artifacts.mkdir()
        self.addCleanup(self.cleanup)
        self.calls = []
        self.fixture_events = []
        self.environment = {"TEST_RUNNER_ATODE_QA_LOOPBACK_URL": "http://127.0.0.1:12345/mock"}
        for name, value in [("ROOT", self.root), ("ARTIFACTS", self.artifacts)]:
            handle = patch.object(module, name, value)
            handle.start()
            self.addCleanup(handle.stop)

    def cleanup(self):
        target = self.root.resolve()
        if target.parent != PREPARED.resolve() or not target.name.startswith("external-build-host-test-"):
            raise ValueError("Cleanup target escaped task artifacts")
        shutil.rmtree(target)

    def result(self):
        return json.loads((self.artifacts / "ios-build-result.json").read_text())

    @contextmanager
    def fixtures(self, udid):
        self.assertEqual(udid, "SELECTED-CI-SIMULATOR")
        self.fixture_events.append("entered")
        try:
            from types import SimpleNamespace
            yield SimpleNamespace(environment=self.environment)
        finally:
            self.fixture_events.append("closed")

    def pipeline(self, scope="all", signing=True, build_exit=0, test_exit=0, fixture=None, fail_launch=False):
        def execute(arguments, log_name, environment=None):
            self.calls.append((arguments, environment))
            if fail_launch and "test-without-building" in arguments:
                raise FileNotFoundError("Mock test executable missing")
            return (test_exit if "test-without-building" in arguments else build_exit if "build-for-testing" in arguments else 0), ""
        with patch.object(module.platform, "system", return_value="Darwin"), \
             patch.object(module.shutil, "which", return_value="/usr/bin/xcodebuild"), \
             patch.object(module, "generate", lambda: None), \
             patch.object(module, "select_simulator", lambda: {"name": "CI iPhone", "udid": "SELECTED-CI-SIMULATOR"}), \
             patch.object(module, "execute", side_effect=execute), \
             patch.object(module, "external_fixtures", fixture or self.fixtures), redirect_stdout(io.StringIO()):
            return module.main(scope, signing, external_input_qa=True)

    def testExternalQAScopeAndSigningMustBeExplicit(self):
        for scope, signing in [("build", True), ("unit", True), ("all", False)]:
            self.assertEqual(self.pipeline(scope, signing), 1)
            self.assertEqual(self.calls, [])
            self.assertEqual(self.fixture_events, [])
            self.assertEqual(self.result()["tests"], "NOT_RUN")

    def testOnlyTestProcessReceivesFixtureEnvironmentAndContextCloses(self):
        self.assertEqual(self.pipeline(), 0)
        self.assertEqual(self.calls[2][0][-1], "build-for-testing")
        self.assertIn("test-without-building", self.calls[-1][0])
        self.assertTrue(all(environment is None for _, environment in self.calls[:-1]))
        self.assertEqual(self.calls[-1][1], self.environment)
        self.assertEqual(self.fixture_events, ["entered", "closed"])
        self.assertEqual(self.result()["tests"], "PASS")

    def testFailedBuildNeverCreatesFixturesOrStartsTests(self):
        self.assertEqual(self.pipeline(build_exit=65), 1)
        self.assertEqual(self.fixture_events, [])
        self.assertEqual(self.result()["tests"], "NOT_RUN")

    def testFailedXCTestPreservesFailureAndClosesServer(self):
        self.assertEqual(self.pipeline(test_exit=65), 1)
        self.assertEqual(self.fixture_events, ["entered", "closed"])
        self.assertEqual(self.result()["test_exit_code"], 65)
        self.assertEqual(self.result()["tests"], "FAIL")

    def testFailedFixturePreparationDoesNotStartXCTestOrPreserveStalePass(self):
        (self.artifacts / "ios-build-result.json").write_text('{"tests":"PASS"}')
        def failure(_):
            raise RuntimeError("Fixture setup failed")
        self.assertEqual(self.pipeline(fixture=failure), 1)
        self.assertEqual(len(self.calls), 3)
        self.assertEqual(self.result()["tests"], "NOT_RUN")
        self.assertIn("Fixture setup failed", self.result()["reason"])

    def testCleanupExceptionCannotLeavePassResult(self):
        @contextmanager
        def failure(udid):
            with self.fixtures(udid) as fixture:
                yield fixture
                raise OSError("Fixture cleanup failed")
        self.assertEqual(self.pipeline(fixture=failure), 1)
        self.assertEqual(self.fixture_events, ["entered", "closed"])
        self.assertIn("Fixture cleanup failed", self.result()["errors"][0])
        self.assertNotEqual(self.result()["tests"], "PASS")

    def testTestLaunchExceptionStillClosesFixtureServer(self):
        self.assertEqual(self.pipeline(fail_launch=True), 1)
        self.assertEqual(self.fixture_events, ["entered", "closed"])
        self.assertEqual(self.result()["tests"], "NOT_RUN")
        self.assertIsNone(self.result()["test_exit_code"])
        self.assertIn("Mock test executable missing", self.result()["errors"][0])

    def testExecuteInheritsEnvironmentAndDoesNotPrintIt(self):
        script = "import os; print(os.environ['ATODE_HOST_ENV_MARKER']); print(os.environ['TEST_RUNNER_ATODE_QA_LOOPBACK_URL'])"
        with patch.dict(os.environ, {"ATODE_HOST_ENV_MARKER": "inherited"}), redirect_stdout(io.StringIO()):
            code, output = module.execute([sys.executable, "-c", script], "env-test.log", self.environment)
        self.assertEqual(code, 0)
        self.assertIn("inherited", output)
        self.assertIn(self.environment["TEST_RUNNER_ATODE_QA_LOOPBACK_URL"], output)
        self.assertNotIn("PATH=", output)


if __name__ == "__main__":
    unittest.main()
