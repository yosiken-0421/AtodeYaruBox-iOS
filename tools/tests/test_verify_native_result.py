"""Host tests ensure an exit-zero runner cannot conceal skipped/missing native tests."""
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import tempfile
import unittest
from tools import verify_native_result as gate


class NativeEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="atode-native-evidence-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        for folder in ["Tests", "UITests", "artifacts/Tests-fresh.xcresult"]:
            (self.root / folder).mkdir(parents=True)
        (self.root / "Tests/Example.swift").write_text("final class ExampleTests: XCTestCase { func testSave() {} }", encoding="utf-8")
        (self.root / "UITests/Flow.swift").write_text("final class FlowTests: XCTestCase { func testLaunch() {} }", encoding="utf-8")
        self.now = datetime.now(timezone.utc)
        self.result = {"build": "PASS", "tests": "PASS", "scope": "all", "build_exit_code": 0,
            "test_exit_code": 0, "started_at": (self.now - timedelta(minutes=1)).isoformat(),
            "finished_at": self.now.isoformat(), "logs": ["test-fresh.log"],
            "result_bundle": "Tests-fresh.xcresult", "warnings": [], "errors": []}
        self.log = "Test Case '-[AtodeYaruBoxTests.ExampleTests testSave]' passed (0.010 seconds).\nTest Case 'FlowTests.testLaunch' passed (1.0 seconds).\n"

    def inspect(self):
        (self.root / "artifacts/ios-build-result.json").write_text(json.dumps(self.result), encoding="utf-8")
        (self.root / "artifacts/test-fresh.log").write_text(self.log, encoding="utf-8")
        return gate.inspect(self.root, 1, 1, self.now)

    def testActualPassRequiresEveryUnitAndUITest(self):
        report = self.inspect()
        self.assertEqual(report["status"], "PASS")
        self.assertEqual((report["unit_passed"], report["ui_passed"]), (1, 1))

    def testExitZeroWithNoCasesIsRejected(self):
        self.log = "** TEST SUCCEEDED **"
        report = self.inspect()
        self.assertEqual(report["status"], "FAIL")
        self.assertFalse(report["native_xctest"])

    def testMultilineAssertionRetainsOCRDateWithoutNextCaseOutput(self):
        self.log = (
            "Test Case '-[AtodeYaruBoxTests.ExampleTests testSave]' started.\n"
            "/clone/Tests/Example.swift:62: error: -[AtodeYaruBoxTests.ExampleTests testSave] : XCTAssertTrue failed - Reservation number: BOOK123\n"
            "2030/10/09 08:00\n"
            "Test Case '-[AtodeYaruBoxTests.ExampleTests testSave]' failed (0.01 seconds).\n"
            "Test Case 'FlowTests.testLaunch' passed (1.0 seconds).\n"
        )
        self.result["errors"] = [self.log.splitlines()[1]]
        report = self.inspect()
        self.assertTrue(report["native_xctest"])
        self.assertEqual(report["status"], "FAIL")
        message = "\n".join(report["case_errors"]["ExampleTests.testSave"])
        self.assertIn("2030/10/09 08:00", message)
        self.assertNotIn("FlowTests", message)

    def testSkippedFailedAndRerunCasesAreRejected(self):
        for outcome in ["skipped", "failed"]:
            with self.subTest(outcome=outcome):
                original = self.log
                self.log = original.replace("testSave]' passed", "testSave]' " + outcome)
                self.assertEqual(self.inspect()["status"], "FAIL")
                self.log = original
        self.log += "Test Case 'ExampleTests.testSave' passed (0.1 seconds).\n"
        self.assertEqual(self.inspect()["status"], "FAIL")

    def testStaleOrIncompleteBuildDoesNotReuseSuccess(self):
        self.result["finished_at"] = (self.now - timedelta(hours=2)).isoformat()
        self.assertEqual(self.inspect()["status"], "FAIL")
        self.result["finished_at"] = self.now.isoformat()
        self.result["test_exit_code"] = None
        self.assertEqual(self.inspect()["status"], "FAIL")

    def testMissingResultBundleIsRejected(self):
        self.result["result_bundle"] = "Absent.xcresult"
        self.assertEqual(self.inspect()["status"], "FAIL")
        self.result["result_bundle"] = "../Tests-fresh.xcresult"
        self.assertEqual(self.inspect()["status"], "FAIL")

    def testSwiftWarningsAreDistinguishedFromToolNotices(self):
        self.result["warnings"] = ["/clone/View.swift:12:5: warning: deprecated API", "warning: metadata extraction skipped"]
        report = self.inspect()
        self.assertEqual(report["compiler_warnings"], [self.result["warnings"][0]])
        self.assertEqual(len(report["warnings"]), 2)

    def testUnexpectedCasesOrRecordedErrorsRejectAcceptance(self):
        self.log += "Test Case 'UnexpectedTests.testOther' passed (0.1 seconds).\n"
        self.assertEqual(self.inspect()["status"], "FAIL")
        self.result["errors"] = ["error: actual compiler diagnostic"]
        self.assertEqual(self.inspect()["status"], "FAIL")


if __name__ == "__main__":
    unittest.main()
