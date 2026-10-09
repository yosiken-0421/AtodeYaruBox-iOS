"""Build/test entry point. Every exit records fresh, truthful native execution results."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import uuid

if __package__:
    from .generate_project import main as generate
else:
    from generate_project import main as generate

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts"


def execute(arguments, log_name, environment=None):
    log_path = ARTIFACTS / log_name
    with log_path.open("w", encoding="utf-8") as log:
        with subprocess.Popen(arguments, cwd=ROOT, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True,
                              encoding="utf-8", errors="replace", bufsize=1,
                              env=None if environment is None else {**os.environ, **environment}) as process:
            lines = []
            for line in process.stdout:
                lines.append(line)
                log.write(line)
                print(line, end="", flush=True)
            return process.wait(), "".join(lines)


def write_result(result):
    # Replace an old PASS before preflight; a crash cannot leave a stale success.
    name = "ios-release-build-result.json" if result.get("configuration") == "Release" else "ios-build-result.json"
    path = ARTIFACTS / name
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def external_fixtures(udid):
    if __package__:
        from .native_qa_fixtures import NativeQAFixtures
    else:
        from native_qa_fixtures import NativeQAFixtures
    return NativeQAFixtures(ROOT, udid)


def main(scope="all", simulator_signing=False, external_input_qa=False, configuration="Debug"):
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    result = {"build": "NOT_RUN", "tests": "NOT_RUN", "scope": scope, "configuration": configuration,
              "stage": "preflight", "started_at": datetime.now(timezone.utc).isoformat(),
              "finished_at": None, "build_exit_code": None, "test_exit_code": None,
              "warnings": [], "errors": [], "logs": [], "result_bundle": None,
              "simulator": None, "udid": None, "reason": "Execution in progress",
              "simulator_signing": "LOCAL_AD_HOC" if simulator_signing else "DISABLED",
              "external_input_qa": external_input_qa}
    write_result(result)
    logs = []
    exit_code = 1
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]

    def run(arguments, name, environment=None):
        log_name = configuration.lower() + "-" + name + "-" + stamp + ".log"
        result["logs"].append(log_name)
        code, output = (execute(arguments, log_name) if environment is None
                        else execute(arguments, log_name, environment=environment))
        logs.append(output)
        return code

    try:
        if configuration not in {"Debug", "Release"} or (configuration == "Release" and scope != "build"):
            raise ValueError("Release verification is a separate Simulator build; full XCTest acceptance uses Debug")
        if scope not in {"build", "unit", "all"}:
            raise ValueError("Unknown test scope")
        if external_input_qa and (scope != "all" or not simulator_signing):
            raise ValueError("External input QA requires all tests and local Simulator signing")
        if platform.system() != "Darwin" or not shutil.which("xcodebuild"):
            result["reason"] = "macOS and full Xcode with iOS Simulator are required"
            exit_code = 2
        else:
            generate()
            for arguments, name in [(["xcodebuild", "-version"], "xcode-version"),
                                    (["plutil", "-lint", "AtodeYaruBox.xcodeproj/project.pbxproj"], "project-lint")]:
                if run(arguments, name) != 0:
                    raise RuntimeError(name + " preflight failed; see the corresponding log")
            destination = "generic/platform=iOS Simulator"
            if scope != "build":
                device = select_simulator()
                result["simulator"], result["udid"] = device["name"], device["udid"]
                destination = "platform=iOS Simulator,id=" + device["udid"]
            else:
                result["simulator"] = "Generic Simulator build"
            base = ["xcodebuild", "-project", "AtodeYaruBox.xcodeproj", "-scheme", "AtodeYaruBox",
                    "-configuration", configuration, "-destination", destination,
                    "-derivedDataPath", str(ROOT / ("DerivedDataRelease" if configuration == "Release" else "DerivedData"))]
            if simulator_signing:
                # This destination is always a Simulator. No developer identity,
                # provisioning service, certificate or physical-device signing.
                base += ["CODE_SIGNING_ALLOWED=YES", "CODE_SIGNING_REQUIRED=NO", "CODE_SIGN_IDENTITY=-",
                         "CODE_SIGN_STYLE=Manual", "DEVELOPMENT_TEAM=", "PROVISIONING_PROFILE_SPECIFIER="]
            else:
                base.append("CODE_SIGNING_ALLOWED=NO")
            result["stage"] = "build"
            result["build_action"] = "build" if scope == "build" else "build-for-testing"
            write_result(result)
            code = run(base + [result["build_action"]], "build")
            result["build_exit_code"] = code
            result["build"] = "PASS" if code == 0 else "FAIL"
            if code != 0:
                result["reason"] = "iOS build failed; tests were not started"
            elif scope == "build":
                result["reason"] = "iOS build succeeded; tests were outside the requested scope"
                exit_code = 0
            else:
                result["stage"] = "tests"
                result["result_bundle"] = "Tests-" + stamp + ".xcresult"
                write_result(result)
                arguments = base + ["test-without-building", "-parallel-testing-enabled", "NO",
                    "-resultBundlePath", str(ARTIFACTS / result["result_bundle"])]
                if scope == "unit":
                    arguments += ["-only-testing:AtodeYaruBoxTests"]
                if external_input_qa:
                    with external_fixtures(result["udid"]) as fixture:
                        code = run(arguments, "test", environment=fixture.environment)
                else:
                    code = run(arguments, "test")
                result["test_exit_code"] = code
                result["tests"] = "PASS" if code == 0 else "FAIL"
                result["reason"] = "iOS build and requested tests succeeded" if code == 0 else "iOS tests failed"
                exit_code = 0 if code == 0 else 1
    except Exception as error:
        result["reason"] = type(error).__name__ + ": " + str(error)
        result["errors"].append(result["reason"])
    except KeyboardInterrupt:
        result["reason"] = "Build/test execution was interrupted"
        exit_code = 130
    finally:
        for line in "\n".join(logs).splitlines():
            if "warning:" in line:
                result["warnings"].append(line.strip())
            if "error:" in line:
                result["errors"].append(line.strip())
        result["warnings"] = sorted(set(result["warnings"]))
        result["errors"] = list(dict.fromkeys(result["errors"]))
        result["finished_at"] = datetime.now(timezone.utc).isoformat()
        write_result(result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return exit_code


def select_simulator():
    requested = os.environ.get("ATODE_QA_IOS_RUNTIME")
    if requested is not None and not re.fullmatch(r"(?:1[7-9]|[2-9][0-9])\.[0-9]{1,2}", requested):
        raise ValueError("Invalid requested QA iOS runtime")
    requested_version = tuple(map(int, requested.split("."))) if requested else None
    raw = subprocess.check_output(["xcrun", "simctl", "list", "devices", "available", "--json"],
                                  text=True, encoding="utf-8", stderr=subprocess.STDOUT)
    inventory = json.loads(raw)
    phones = []
    for runtime, devices in inventory.get("devices", {}).items():
        version = re.search(r"iOS-(\d+)-(\d+)", runtime)
        if not version or int(version.group(1)) < 17:
            continue
        if requested_version and tuple(map(int, version.groups())) != requested_version:
            continue
        for device in devices:
            if device.get("isAvailable") and device.get("name", "").startswith("iPhone") and device.get("udid"):
                phones.append(((int(version.group(1)), int(version.group(2))), device))
    if not phones:
        if requested:
            raise RuntimeError("Requested iOS Simulator " + requested + " is not installed")
        raise RuntimeError("No available iOS 17+ iPhone Simulator; install a compatible runtime before retrying")
    device = sorted(phones, key=lambda entry: (entry[0], entry[1]["name"]), reverse=True)[0][1]
    print("Using Simulator:", device["name"], device["udid"])
    if device.get("state") != "Booted":
        subprocess.run(["xcrun", "simctl", "boot", device["udid"]], check=True, cwd=ROOT)
    boot = subprocess.run(["xcrun", "simctl", "bootstatus", device["udid"], "-b"],
                          check=True, cwd=ROOT, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, text=True, timeout=180)
    print(boot.stdout, flush=True)
    # Some hosted runtime images return exit zero for a terminal migration
    # failure. Such a guest cannot provide valid Photos or UI test evidence.
    if "data migration failed" in boot.stdout.casefold():
        raise RuntimeError("Selected Simulator data migration failed before testing")
    return device


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", choices=["build", "unit", "all"], default="all")
    parser.add_argument("--simulator-signing", action="store_true")
    parser.add_argument("--external-input-qa", action="store_true")
    parser.add_argument("--configuration", choices=["Debug", "Release"], default="Debug")
    args = parser.parse_args()
    sys.exit(main(args.scope, args.simulator_signing, args.external_input_qa, args.configuration))
