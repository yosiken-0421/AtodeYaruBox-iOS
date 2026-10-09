"""Host-side automation tests; these do not execute Xcode or XCTest."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools import build_mac


class BuildResultTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="atode-build-test-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.artifacts = self.root / "artifacts"
        self.artifacts.mkdir()
        self.commands = []
        for name, value in [("ROOT", self.root), ("ARTIFACTS", self.artifacts)]:
            replacement = patch.object(build_mac, name, value)
            replacement.start()
            self.addCleanup(replacement.stop)

    def result(self):
        return json.loads((self.artifacts / "ios-build-result.json").read_text(encoding="utf-8"))

    def run_pipeline(self, scope="all", responses=None, simulator_signing=False, **overrides):
        values = iter(responses or [(0, "")] * 4)

        def fake_execute(arguments, log_name):
            self.commands.append(arguments)
            return next(values)

        defaults = {"generate": lambda: None,
                    "select_simulator": lambda: {"name": "iPhone Test", "udid": "TEST-UDID"},
                    "execute": fake_execute}
        defaults.update(overrides)
        with patch.object(build_mac.platform, "system", return_value="Darwin"), \
             patch.object(build_mac.shutil, "which", return_value="/usr/bin/xcodebuild"), \
             patch.multiple(build_mac, **defaults), redirect_stdout(io.StringIO()):
            return build_mac.main(scope, simulator_signing)

    def testUnsupportedHostReplacesStaleSuccess(self):
        (self.artifacts / "ios-build-result.json").write_text('{"build":"PASS","tests":"PASS"}')
        with patch.object(build_mac.platform, "system", return_value="Windows"), \
             patch.object(build_mac, "execute") as execute, redirect_stdout(io.StringIO()):
            self.assertEqual(build_mac.main(), 2)
        execute.assert_not_called()
        self.assertEqual((self.result()["build"], self.result()["tests"]), ("NOT_RUN", "NOT_RUN"))
        self.assertIsNotNone(self.result()["finished_at"])

    def testClearsPreviousPassBeforeProjectGenerationAndRecordsFailure(self):
        (self.artifacts / "ios-build-result.json").write_text('{"build":"PASS"}')

        def failed_generation():
            self.assertEqual(self.result()["build"], "NOT_RUN")
            self.assertIsNone(self.result()["finished_at"])
            raise OSError("Cannot generate project")

        self.assertEqual(self.run_pipeline(generate=failed_generation), 1)
        self.assertEqual(self.result()["build"], "NOT_RUN")
        self.assertIn("Cannot generate project", self.result()["reason"])
        self.assertEqual(len(self.commands), 0)

    def testFailedPreflightNeverStartsBuild(self):
        self.assertEqual(self.run_pipeline(responses=[(0, "Xcode"), (1, "error: invalid plist")]), 1)
        result = self.result()
        self.assertEqual(len(self.commands), 2)
        self.assertEqual(result["stage"], "preflight")
        self.assertEqual((result["build"], result["tests"]), ("NOT_RUN", "NOT_RUN"))
        self.assertIn("error: invalid plist", result["errors"])
        self.assertTrue(any("project-lint" in name for name in result["logs"]))

    def testSimulatorFailureLeavesNativeExecutionNotRun(self):
        def failed_simulator():
            raise RuntimeError("Simulator runtime unavailable")
        self.assertEqual(self.run_pipeline(select_simulator=failed_simulator), 1)
        self.assertEqual(self.result()["build"], "NOT_RUN")
        self.assertEqual(len(self.commands), 2)
        self.assertIn("Simulator runtime unavailable", self.result()["reason"])

    def testFailedBuildNeverStartsTests(self):
        self.assertEqual(self.run_pipeline(responses=[(0, ""), (0, ""), (65, "error: Swift compilation failed")]), 1)
        result = self.result()
        self.assertEqual((result["build"], result["tests"]), ("FAIL", "NOT_RUN"))
        self.assertEqual(result["build_exit_code"], 65)
        self.assertIsNone(result["test_exit_code"])
        self.assertEqual(len(self.commands), 3)

    def testFailedTestsPreserveSuccessfulBuildAndFailureExit(self):
        self.assertEqual(self.run_pipeline(responses=[(0, ""), (0, ""), (0, ""), (65, "error: Assertion failed")]), 1)
        result = self.result()
        self.assertEqual((result["build"], result["tests"]), ("PASS", "FAIL"))
        self.assertEqual(result["test_exit_code"], 65)
        self.assertIn("-resultBundlePath", self.commands[-1])

    def testBuildOnlyDoesNotRequireSimulatorOrRunTests(self):
        def unexpected_simulator():
            self.fail("Build-only must use the generic destination")
        self.assertEqual(self.run_pipeline("build", select_simulator=unexpected_simulator), 0)
        self.assertEqual(self.result()["tests"], "NOT_RUN")
        self.assertEqual(len(self.commands), 3)
        self.assertIn("generic/platform=iOS Simulator", self.commands[-1])
        self.assertEqual(self.commands[-1][-1], "build")

    def testUnitScopeAndAllScopeChooseCorrectTests(self):
        self.assertEqual(self.run_pipeline("unit"), 0)
        self.assertEqual(self.commands[2][-1], "build-for-testing")
        self.assertIn("test-without-building", self.commands[-1])
        self.assertIn("-only-testing:AtodeYaruBoxTests", self.commands[-1])
        self.assertIn("platform=iOS Simulator,id=TEST-UDID", self.commands[-1])
        self.assertEqual(self.run_pipeline("all"), 0)
        self.assertFalse(any(value.startswith("-only-testing:") for value in self.commands[-1]))
        self.assertEqual(self.result()["tests"], "PASS")
        self.assertEqual(self.result()["build_action"], "build-for-testing")

    def testAdHocSigningIsLimitedToSimulatorAndDoesNotRequestProvisioning(self):
        self.assertEqual(self.run_pipeline(simulator_signing=True), 0)
        for command in self.commands[2:]:
            self.assertIn("platform=iOS Simulator,id=TEST-UDID", command)
            self.assertIn("CODE_SIGN_IDENTITY=-", command)
            self.assertIn("DEVELOPMENT_TEAM=", command)
            self.assertIn("PROVISIONING_PROFILE_SPECIFIER=", command)
            self.assertNotIn("-allowProvisioningUpdates", command)
        self.assertEqual(self.result()["simulator_signing"], "LOCAL_AD_HOC")

    def testPreflightAndNativeWarningsAreCollectedWithoutDuplication(self):
        responses = [(0, "warning: SDK notice\n"), (0, ""),
                     (0, "warning: Swift notice\n"), (0, "warning: Swift notice\n")]
        self.assertEqual(self.run_pipeline(responses=responses), 0)
        self.assertEqual(self.result()["warnings"], ["warning: SDK notice", "warning: Swift notice"])

    def testFailedTestLaunchDoesNotClaimTestPass(self):
        calls = 0
        def failed_launch(arguments, log_name):
            nonlocal calls
            calls += 1
            if calls == 4:
                raise FileNotFoundError("Test executable missing")
            return 0, ""
        self.assertEqual(self.run_pipeline(execute=failed_launch), 1)
        self.assertEqual((self.result()["build"], self.result()["tests"]), ("PASS", "NOT_RUN"))

    def testInterruptedPipelineWritesACompletedFailureRecord(self):
        def interrupted():
            raise KeyboardInterrupt()
        self.assertEqual(self.run_pipeline(generate=interrupted), 130)
        self.assertEqual(self.result()["build"], "NOT_RUN")
        self.assertIsNotNone(self.result()["finished_at"])
        self.assertIn("interrupted", self.result()["reason"])

    def testResultBundleNamesCannotCollideAcrossConsecutiveRuns(self):
        self.assertEqual(self.run_pipeline(), 0)
        first = self.result()["result_bundle"]
        self.assertEqual(self.run_pipeline(), 0)
        self.assertNotEqual(first, self.result()["result_bundle"])

    def testExecuteCapturesUnicodeStdoutStderrAndFailureExitCode(self):
        script = "import sys; print('保存の確認'); print('error: test failure', file=sys.stderr); sys.exit(3)"
        with redirect_stdout(io.StringIO()):
            code, output = build_mac.execute([sys.executable, "-X", "utf8", "-c", script], "process.log")
        self.assertEqual(code, 3)
        self.assertIn("保存の確認", output)
        self.assertIn("error: test failure", output)
        self.assertEqual((self.artifacts / "process.log").read_text(encoding="utf-8"), output)


class SimulatorSelectionTests(unittest.TestCase):
    def setUp(self):
        environment = patch.dict(build_mac.os.environ, {}, clear=False)
        environment.start()
        self.addCleanup(environment.stop)
        build_mac.os.environ.pop("ATODE_QA_IOS_RUNTIME", None)

    def select(self, devices):
        with patch.object(build_mac.subprocess, "check_output", return_value=json.dumps({"devices": devices})), \
             patch.object(build_mac.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, stdout="Boot finished")) as run, redirect_stdout(io.StringIO()):
            chosen = build_mac.select_simulator()
        return chosen, run.call_args_list

    def testSelectsNewestAvailableSupportedIPhoneAndBootsIt(self):
        phone = lambda name, udid, available=True: {"name": name, "udid": udid, "isAvailable": available, "state": "Shutdown"}
        device, calls = self.select({"com.apple.CoreSimulator.SimRuntime.iOS-16-4": [phone("iPhone old", "OLD")],
            "com.apple.CoreSimulator.SimRuntime.iOS-18-2": [phone("iPhone older", "OLDER")],
            "com.apple.CoreSimulator.SimRuntime.iOS-26-0": [phone("iPhone newest", "NEW"),
                phone("iPad Pro", "IPAD"), phone("iPhone unavailable", "NO", False)]})
        self.assertEqual(device["udid"], "NEW")
        self.assertEqual(calls[0].args[0], ["xcrun", "simctl", "boot", "NEW"])
        self.assertEqual(calls[1].args[0], ["xcrun", "simctl", "bootstatus", "NEW", "-b"])

    def testBootedPhoneOnlyWaitsForBootStatus(self):
        _, calls = self.select({"iOS-17-5": [{"name": "iPhone", "udid": "BOOTED", "isAvailable": True, "state": "Booted"}]})
        self.assertEqual(len(calls), 1)
        self.assertIn("bootstatus", calls[0].args[0])

    def testExplicitSupportedRuntimeCannotSilentlyUseNewerGuest(self):
        phone = lambda udid: {"name": "iPhone", "udid": udid, "isAvailable": True, "state": "Booted"}
        with patch.dict(build_mac.os.environ, {"ATODE_QA_IOS_RUNTIME": "18.5"}):
            device, _ = self.select({"iOS-18-5": [phone("EXPECTED")], "iOS-26-2": [phone("NEWER")]})
            self.assertEqual(device["udid"], "EXPECTED")
            with self.assertRaisesRegex(RuntimeError, "18.5"):
                self.select({"iOS-26-2": [phone("NEWER")]})

    def testInvalidRuntimeRejectedBeforeSimulatorInventory(self):
        with patch.dict(build_mac.os.environ, {"ATODE_QA_IOS_RUNTIME": "../../bad"}), \
             patch.object(build_mac.subprocess, "check_output") as inventory:
            with self.assertRaises(ValueError):
                build_mac.select_simulator()
            inventory.assert_not_called()

    def testMissingCompatibleRuntimeIsAnError(self):
        with self.assertRaisesRegex(RuntimeError, "iOS 17"):
            self.select({"iOS-16-4": [{"name": "iPhone", "udid": "OLD", "isAvailable": True}]})

    def testMalformedInventoryIsAnError(self):
        with patch.object(build_mac.subprocess, "check_output", return_value="not json"):
            with self.assertRaises(json.JSONDecodeError):
                build_mac.select_simulator()

    def testBootFailureIsAnError(self):
        phone = {"devices": {"iOS-17-0": [{"name": "iPhone", "udid": "TEST", "isAvailable": True}]}}
        with patch.object(build_mac.subprocess, "check_output", return_value=json.dumps(phone)), \
             patch.object(build_mac.subprocess, "run", side_effect=subprocess.CalledProcessError(1, ["xcrun"])), \
             redirect_stdout(io.StringIO()):
            with self.assertRaises(subprocess.CalledProcessError):
                build_mac.select_simulator()

    def testMigrationFailureWithExitZeroIsRejectedBeforeBuild(self):
        phone = {"devices": {"iOS-26-5": [{"name": "iPhone", "udid": "TEST", "isAvailable": True, "state": "Booted"}]}}
        with patch.object(build_mac.subprocess, "check_output", return_value=json.dumps(phone)), \
             patch.object(build_mac.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, stdout="Status=3, isTerminal=YES\nData Migration Failed")), \
             redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(RuntimeError, "data migration failed"):
                build_mac.select_simulator()


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    report = {"kind": "host-build-automation-tests", "tests_executed": result.testsRun,
              "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped),
              "ios_build_executed": False, "xctest_executed": False}
    output = build_mac.ROOT / "artifacts"
    output.mkdir(exist_ok=True)
    (output / "automation-test-result.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    sys.exit(0 if result.wasSuccessful() else 1)
