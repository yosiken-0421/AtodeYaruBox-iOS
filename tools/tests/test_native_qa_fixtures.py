"""Host fixture safety/lifecycle tests; Simulator commands are mocked, HTTP is real."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request
import uuid

PREPARED = Path(__file__).resolve().parents[2] / "artifacts"
ACTIVE_TOOLS = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("native_fixture_prepared", ACTIVE_TOOLS / "native_qa_fixtures.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
UDID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"


class NativeFixtureTests(unittest.TestCase):
    def setUp(self):
        self.root = PREPARED / ("native-fixture-host-test-" + uuid.uuid4().hex)
        self.root.mkdir()
        (self.root / "tools").mkdir()
        (self.root / "tools/loopback_fixture.py").write_bytes((ACTIVE_TOOLS / "loopback_fixture.py").read_bytes())
        self.addCleanup(self.cleanup)
        self.calls = []

    def cleanup(self):
        target = self.root.resolve()
        if target.parent != PREPARED.resolve() or not target.name.startswith("native-fixture-host-test-"):
            raise ValueError("Cleanup target escaped the task artifacts")
        shutil.rmtree(target)

    def inventory(self, state="Booted"):
        return json.dumps({"devices": {"iOS-26-0": [
            {"udid": UDID, "isAvailable": True, "state": state},
            {"udid": "FFFFFFFF-FFFF-FFFF-FFFF-FFFFFFFFFFFF", "isAvailable": True, "state": "Booted"}]}})

    def commands(self, arguments, **kwargs):
        self.calls.append(arguments)
        if arguments[:2] == ["xcrun", "swift"]:
            Path(arguments[-1]).write_bytes(b"mock-generated-fixture")

    def environment(self, state="Booted", run=None):
        from contextlib import ExitStack
        stack = ExitStack()
        stack.enter_context(patch.object(module.platform, "system", return_value="Darwin"))
        stack.enter_context(patch.object(module.subprocess, "check_output", return_value=self.inventory(state)))
        stack.enter_context(patch.object(module.subprocess, "run", side_effect=run or self.commands))
        return stack

    def assertClosed(self, address):
        with self.assertRaises((urllib.error.URLError, ConnectionError, OSError)):
            urllib.request.urlopen(address, timeout=1)

    def testUnsupportedHostDoesNotTouchSimulator(self):
        with patch.object(module.platform, "system", return_value="Windows"), patch.object(module.subprocess, "check_output") as command:
            with self.assertRaisesRegex(RuntimeError, "macOS"):
                with module.NativeQAFixtures(self.root, UDID):
                    self.fail("Unsupported host entered the context")
            command.assert_not_called()

    def testMalformedIdentifierRejectedBeforeAnySimulatorCall(self):
        with self.environment(), patch.object(module.subprocess, "check_output") as command:
            with self.assertRaisesRegex(ValueError, "identifier"):
                with module.NativeQAFixtures(self.root, "-" * 36):
                    self.fail("Malformed identifier accepted")
            command.assert_not_called()

    def testSelectedSimulatorMustAlreadyBeAvailableAndBooted(self):
        with self.environment(state="Shutdown"):
            with self.assertRaisesRegex(RuntimeError, "available and booted"):
                with module.NativeQAFixtures(self.root, UDID):
                    self.fail("Unbooted device accepted")
        self.assertEqual(self.calls, [])

    def testAddsOnlySyntheticPhotoToSelectedDeviceAndClosesRealHTTPServer(self):
        with self.environment():
            with module.NativeQAFixtures(self.root, UDID) as fixture:
                self.assertEqual(set(fixture.environment), {"TEST_RUNNER_ATODE_QA_LOOPBACK_URL"})
                address = fixture.environment["TEST_RUNNER_ATODE_QA_LOOPBACK_URL"]
                self.assertTrue(address.startswith("http://127.0.0.1:"))
                with urllib.request.urlopen(address, timeout=2) as response:
                    self.assertEqual(response.status, 200)
                    self.assertIn(b"ATODE-SAFARI-FIXTURE", response.read())
                    self.assertEqual(response.headers["Cache-Control"], "no-store")
                evidence = json.loads((self.root / "artifacts/external-input-fixtures.json").read_text())
                self.assertEqual(evidence["status"], "FIXTURES_READY_NOT_TEST_RESULT")
                self.assertFalse(evidence["uses_personal_data"])
        self.assertEqual(self.calls[1], ["xcrun", "simctl", "launch", UDID, "com.apple.mobileslideshow"])
        self.assertEqual(self.calls[2][:4], ["xcrun", "simctl", "addmedia", UDID])
        self.assertClosed(address)

    def testColdLibraryTimeoutStopsOnceAndDoesNotStartSafariFixture(self):
        def timeout_import(arguments, **kwargs):
            self.commands(arguments, **kwargs)
            if "addmedia" in arguments:
                self.assertEqual(kwargs["timeout"], 180)
                raise subprocess.TimeoutExpired(arguments, kwargs["timeout"])
        with self.environment(run=timeout_import):
            with self.assertRaises(subprocess.TimeoutExpired):
                with module.NativeQAFixtures(self.root, UDID):
                    self.fail("Timed out image import was accepted")
        evidence = json.loads((self.root / "artifacts/external-input-fixtures.json").read_text())
        self.assertEqual(evidence["status"], "FIXTURE_SETUP_FAILED_NOT_TEST_RESULT")
        self.assertEqual(evidence["stage"], "import_synthetic_image")
        self.assertEqual(sum("addmedia" in command for command in self.calls), 1)

    def testMissingGeneratedImageFailsBeforeAddingMedia(self):
        with self.environment(run=lambda *args, **kwargs: None):
            with self.assertRaisesRegex(RuntimeError, "did not create"):
                with module.NativeQAFixtures(self.root, UDID):
                    self.fail("Missing photo silently accepted")
        evidence = json.loads((self.root / "artifacts/external-input-fixtures.json").read_text())
        self.assertEqual(evidence["status"], "FIXTURE_SETUP_FAILED_NOT_TEST_RESULT")

    def testMediaImportFailureCannotClaimFixturesReady(self):
        def fail_import(arguments, **kwargs):
            self.commands(arguments, **kwargs)
            if "addmedia" in arguments:
                raise subprocess.CalledProcessError(1, arguments)
        with self.environment(run=fail_import):
            with self.assertRaises(subprocess.CalledProcessError):
                with module.NativeQAFixtures(self.root, UDID):
                    self.fail("Import failure silently accepted")
        evidence = json.loads((self.root / "artifacts/external-input-fixtures.json").read_text())
        self.assertEqual(evidence["status"], "FIXTURE_SETUP_FAILED_NOT_TEST_RESULT")

    def testSetupFailureCannotLeaveStaleReadyEvidence(self):
        (self.root / "artifacts").mkdir()
        evidence_path = self.root / "artifacts/external-input-fixtures.json"
        evidence_path.write_text('{"status":"FIXTURES_READY_NOT_TEST_RESULT"}')
        with patch.object(module.platform, "system", return_value="Windows"):
            with self.assertRaises(RuntimeError):
                with module.NativeQAFixtures(self.root, UDID):
                    self.fail("Unsupported host entered")
        evidence = json.loads(evidence_path.read_text())
        self.assertEqual(evidence["status"], "FIXTURE_SETUP_FAILED_NOT_TEST_RESULT")
        self.assertEqual(evidence["failure_type"], "RuntimeError")

    def testFailureInsideTestStillClosesServer(self):
        with self.environment():
            with self.assertRaisesRegex(RuntimeError, "mock XCTest failed"):
                with module.NativeQAFixtures(self.root, UDID) as fixture:
                    address = fixture.environment["TEST_RUNNER_ATODE_QA_LOOPBACK_URL"]
                    raise RuntimeError("mock XCTest failed")
        self.assertClosed(address)


if __name__ == "__main__":
    unittest.main()
