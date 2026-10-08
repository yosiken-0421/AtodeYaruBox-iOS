"""Acceptance gates for actual XCTest logs, independent of the runner's exit status."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
CASE = re.compile(r"^Test Case '(?:-\[([\w.]+) (test\w+)\]|([\w.]+)\.(test\w+))' (passed|failed|skipped)\b", re.MULTILINE)


def expected_cases(root):
    groups = {}
    for folder in ["Tests", "UITests"]:
        cases = set()
        for path in sorted((root / folder).rglob("*.swift")):
            source = path.read_text(encoding="utf-8")
            classes = re.findall(r"\bclass\s+(\w+)\s*:\s*XCTestCase\b", source)
            methods = re.findall(r"\bfunc\s+(test\w+)\s*\(", source)
            if methods and len(classes) != 1:
                raise ValueError("Ambiguous XCTest class: " + path.relative_to(root).as_posix())
            for method in methods:
                case = classes[0] + "." + method
                if case in cases:
                    raise ValueError("Duplicate XCTest method: " + case)
                cases.add(case)
        groups[folder] = cases
    if groups["Tests"] & groups["UITests"]:
        raise ValueError("Unit/UI XCTest names overlap")
    return groups


def read_cases(text):
    outcomes = {}
    for match in CASE.finditer(text):
        class_name, method = (match[1], match[2]) if match[1] else (match[3], match[4])
        key = class_name.rsplit(".", 1)[-1] + "." + method
        outcomes.setdefault(key, []).append(match[5])
    return outcomes


def inspect(root, expected_unit, expected_ui, now=None):
    now = now or datetime.now(timezone.utc)
    artifacts = root / "artifacts"
    raw = json.loads((artifacts / "ios-build-result.json").read_text(encoding="utf-8"))
    groups = expected_cases(root)
    problems = []
    if len(groups["Tests"]) != expected_unit or len(groups["UITests"]) != expected_ui:
        problems.append("Authored test counts differ from the declared CI acceptance gate")
    if raw.get("build") != "PASS" or raw.get("tests") != "PASS" or raw.get("scope") != "all":
        problems.append("The actual iOS build and full XCTest run did not both pass")
    if raw.get("build_exit_code") != 0 or raw.get("test_exit_code") != 0:
        problems.append("Native runner exit codes are missing or nonzero")
    try:
        start = datetime.fromisoformat(raw["started_at"])
        finish = datetime.fromisoformat(raw["finished_at"])
        if not start.tzinfo or not finish.tzinfo or not (start <= finish <= now + timedelta(minutes=1)):
            raise ValueError("Invalid timestamps")
        if now - finish > timedelta(hours=1):
            problems.append("Stale native build result")
    except (KeyError, TypeError, ValueError):
        problems.append("Native execution timestamps are missing or invalid")
    bundle = raw.get("result_bundle") or ""
    if not bundle or Path(bundle).name != bundle or not bundle.endswith(".xcresult") or not (artifacts / bundle).is_dir():
        problems.append("Actual XCTest result bundle is missing")
    logs = [name for name in raw.get("logs", []) if re.fullmatch(r"test-[\w-]+\.log", name)]
    text = ""
    if len(logs) != 1:
        problems.append("Expected exactly one actual XCTest execution log")
        outcomes = {}
    else:
        path = artifacts / logs[0]
        if not path.is_file() or path.stat().st_size > 32 * 1024 * 1024:
            problems.append("Actual XCTest log missing or too large")
            outcomes = {}
        else:
            text = path.read_text(encoding="utf-8")
            outcomes = read_cases(text)
    expected = groups["Tests"] | groups["UITests"]
    passed = {case for case, values in outcomes.items() if values == ["passed"]}
    missing = sorted(expected - passed)
    unexpected = sorted(outcomes.keys() - expected)
    bad = sorted(case for case, values in outcomes.items() if values != ["passed"])
    case_errors = {}
    for case in bad:
        class_name, method = case.split(".", 1)
        entries = []
        lines = text.splitlines()
        for index, line in enumerate(lines):
            if "error:" not in line or not (class_name + " " + method in line or case in line):
                continue
            block = [line.strip()]
            for next_line in lines[index + 1:index + 13]:
                if next_line.startswith(("Test Case '", "Test Suite '")) or "error:" in next_line:
                    break
                block.append(next_line)
            entries.append("\n".join(block)[:4000])
        case_errors[case] = entries
    if missing: problems.append("Tests missing a single recorded pass: " + ", ".join(missing))
    if unexpected: problems.append("Unexpected tests: " + ", ".join(unexpected))
    if bad: problems.append("Failed, skipped or repeated test executions: " + ", ".join(bad))
    if raw.get("errors"): problems.append("Native execution recorded errors")
    warnings = raw.get("warnings", [])
    compiler_warnings = [line for line in warnings if re.search(r"\.swift:\d+(?::\d+)?:\s*warning:|(?:Swift|clang|ld):\s*warning:", line)]
    return {"status": "PASS" if not problems else "FAIL",
        "native_xctest": raw.get("test_exit_code") is not None and bool(outcomes),
        "unit_passed": len(groups["Tests"] & passed), "unit_expected": len(groups["Tests"]),
        "ui_passed": len(groups["UITests"] & passed), "ui_expected": len(groups["UITests"]),
        "failed_or_skipped": bad, "missing": missing, "problems": problems,
        "warnings": warnings, "compiler_warnings": compiler_warnings, "errors": raw.get("errors", []),
        "source_sha": __import__("os").environ.get("CM_COMMIT"),
        "checked_at": now.isoformat(), "cases": outcomes, "case_errors": case_errors}


def junit(report, path):
    suite = ET.Element("testsuite", name="AtodeYaruBox native XCTest", tests=str(len(report["cases"])),
                       failures=str(len(report["failed_or_skipped"])))
    for name, outcomes in sorted(report["cases"].items()):
        class_name, method = name.split(".", 1)
        case = ET.SubElement(suite, "testcase", classname=class_name, name=method)
        if outcomes != ["passed"]:
            details = "\n".join(report.get("case_errors", {}).get(name, [])) or ", ".join(outcomes)
            ET.SubElement(case, "failure", message=details[:2000]).text = details
    ET.indent(suite)
    ET.ElementTree(suite).write(path, encoding="utf-8", xml_declaration=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-unit", type=int, required=True)
    parser.add_argument("--expected-ui", type=int, required=True)
    parser.add_argument("--require-no-compiler-warnings", action="store_true")
    args = parser.parse_args()
    path = ROOT / "artifacts/native-acceptance.json"
    # Never reuse an old PASS if loading fresh native evidence fails.
    path.parent.mkdir(exist_ok=True)
    path.write_text('{"status":"NOT_VERIFIED"}', encoding="utf-8")
    try:
        report = inspect(ROOT, args.expected_unit, args.expected_ui)
        if args.require_no_compiler_warnings and report["compiler_warnings"]:
            report["problems"].append("Swift/compiler warnings must be fixed")
            report["status"] = "FAIL"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        junit(report, ROOT / "artifacts/native-tests.xml")
        print(json.dumps(report, ensure_ascii=True))
        return 0 if report["status"] == "PASS" else 1
    except (OSError, ValueError, TypeError) as error:
        print("Native evidence rejected: " + str(error))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
