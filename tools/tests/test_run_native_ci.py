"""Failure reporting must never turn a failed native test into a successful CI run."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from tools import run_native_ci


class NativeCIRunnerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="atode-native-ci-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / "artifacts").mkdir()

    def run_case(self, build_code, report):
        with patch.object(run_native_ci, "ROOT", self.root), \
             patch.object(run_native_ci, "build", return_value=build_code), \
             patch.object(run_native_ci, "inspect", return_value=report), \
             patch.object(run_native_ci, "junit") as junit:
            code = run_native_ci.main()
        junit.assert_called_once()
        saved = json.loads((self.root / "artifacts/native-acceptance.json").read_text(encoding="utf-8"))
        self.assertEqual(saved, report)
        return code

    def testFailedNativeRunStillProducesReportAndRemainsFailure(self):
        self.assertEqual(self.run_case(1, {"status": "FAIL", "cases": {}}), 1)

    def testExitZeroDoesNotHideMissingOrSkippedXCTest(self):
        self.assertEqual(self.run_case(0, {"status": "FAIL", "cases": {}}), 1)

    def testValidNativePassPreservesSuccess(self):
        self.assertEqual(self.run_case(0, {"status": "PASS", "cases": {"Case.test": ["passed"]}}), 0)

    def testSimulatorSigningOptionPreservesNativeFailure(self):
        with patch.object(run_native_ci, "ROOT", self.root), \
             patch.object(run_native_ci, "build", return_value=1) as build, \
             patch.object(run_native_ci, "inspect", return_value={"status": "FAIL", "cases": {}}), \
             patch.object(run_native_ci, "junit"):
            self.assertEqual(run_native_ci.main(simulator_signing=True), 1)
        build.assert_called_once_with("all", simulator_signing=True, external_input_qa=False)

    def testExternalInputQAFlagAnd86CaseAcceptanceReachNativeRunner(self):
        with patch.object(run_native_ci, "ROOT", self.root), \
             patch.object(run_native_ci, "build", return_value=0) as build, \
             patch.object(run_native_ci, "inspect", return_value={"status": "PASS", "cases": {}}) as inspect, \
             patch.object(run_native_ci, "junit"):
            self.assertEqual(run_native_ci.main(simulator_signing=True, external_input_qa=True), 0)
        build.assert_called_once_with("all", simulator_signing=True, external_input_qa=True)
        inspect.assert_called_once_with(self.root, 76, 10)


if __name__ == "__main__":
    unittest.main()
