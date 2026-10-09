"""Synthetic photo and loopback fixtures for the selected CI Simulator only."""
from contextlib import ExitStack
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import subprocess


class NativeQAFixtures:
    def __init__(self, root, udid):
        self.root = Path(root).resolve()
        self.udid = udid
        self.stack = ExitStack()
        self.photo_import_attempts = 0
        self.photo_recovery_stage = None
        self.initial_photo_import_failure = None

    def record(self, status, **details):
        artifacts = self.root / "artifacts"
        artifacts.mkdir(exist_ok=True)
        (artifacts / "external-input-fixtures.json").write_text(json.dumps({
            "status": status, "loopback_only": True, "uses_personal_data": False,
            "photo_import_attempts": self.photo_import_attempts,
            "photo_recovery_stage": self.photo_recovery_stage,
            "initial_photo_import_failure": self.initial_photo_import_failure, **details,
        }, indent=2), encoding="utf-8")

    def import_synthetic_photo(self, image):
        arguments = ["xcrun", "simctl", "addmedia", self.udid, str(image)]
        self.photo_import_attempts = 1
        try:
            subprocess.run(arguments, cwd=self.root, check=True, timeout=180)
            return
        except subprocess.TimeoutExpired:
            # Recover fixture setup once, before any XCTest execution. Never
            # erase data, restart other guests, retry tests, or accept a timeout.
            self.initial_photo_import_failure = "TimeoutExpired"
            if os.environ.get("GITHUB_ACTIONS") != "true" or os.environ.get("RUNNER_ENVIRONMENT") != "github-hosted":
                self.photo_recovery_stage = "not_permitted_outside_hosted_ci"
                raise
            self.photo_recovery_stage = "shutdown"
            self.record("FIXTURE_RECOVERING_NOT_TEST_RESULT", stage="import_synthetic_image")
            self.capture_guest()
            subprocess.run(["xcrun", "simctl", "shutdown", self.udid],
                           cwd=self.root, check=True, timeout=60)
            self.photo_recovery_stage = "boot"
            subprocess.run(["xcrun", "simctl", "boot", self.udid],
                           cwd=self.root, check=True, timeout=60)
            self.photo_recovery_stage = "bootstatus"
            boot = subprocess.run(["xcrun", "simctl", "bootstatus", self.udid, "-b"],
                                  cwd=self.root, check=True, timeout=180,
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            if "data migration failed" in boot.stdout.casefold():
                raise RuntimeError("Selected QA Simulator data migration failed during photo recovery")
            # Import without relaunching the stock Photos UI after the reboot.
            # A second failure remains a setup failure and blocks acceptance.
            self.photo_recovery_stage = "second_import"
            self.photo_import_attempts = 2
            subprocess.run(arguments, cwd=self.root, check=True, timeout=180)
            self.photo_recovery_stage = "completed"

    def capture_guest(self):
        image = self.root / "artifacts/fixture-setup-failure.png"
        try:
            subprocess.run(["xcrun", "simctl", "io", self.udid, "screenshot", str(image)],
                           cwd=self.root, check=True, timeout=15)
            return image.name if image.is_file() else None
        except (OSError, subprocess.SubprocessError):
            return None

    def __enter__(self):
        # Invalidate earlier ready evidence even when setup cannot get past preflight.
        self.record("FIXTURE_PREPARING_NOT_TEST_RESULT")
        stage = "validate_simulator"
        try:
            if platform.system() != "Darwin":
                raise RuntimeError("Native input QA requires the selected macOS CI Simulator")
            if not re.fullmatch(r"[A-Fa-f0-9]{8}(?:-[A-Fa-f0-9]{4}){3}-[A-Fa-f0-9]{12}", self.udid):
                raise ValueError("Invalid Simulator identifier")
            inventory = json.loads(subprocess.check_output(
                ["xcrun", "simctl", "list", "devices", "available", "--json"], text=True))
            devices = [device for group in inventory.get("devices", {}).values() for device in group]
            matches = [device for device in devices if device.get("udid") == self.udid]
            if len(matches) != 1 or not matches[0].get("isAvailable") or matches[0].get("state") != "Booted":
                raise RuntimeError("Selected QA Simulator is not available and booted")
            artifacts = self.root / "artifacts"
            artifacts.mkdir(exist_ok=True)
            image = artifacts / "synthetic-ocr-photo.png"
            stage = "generate_synthetic_image"
            subprocess.run(["xcrun", "swift", str(self.root / "tools/generate_photo_fixture.swift"), str(image)],
                           cwd=self.root, check=True, timeout=180)
            if not image.is_file() or image.stat().st_size == 0:
                raise RuntimeError("Synthetic photo generator did not create the fixture")
            # simctl imports into the selected booted guest's media library.
            # Opening the stock Photos UI first is unnecessary and can stall
            # on a cold hosted guest before the actual image import starts.
            stage = "import_synthetic_image"
            self.import_synthetic_photo(image)
            stage = "start_loopback_fixture"
            module_path = self.root / "tools/loopback_fixture.py"
            spec = importlib.util.spec_from_file_location("atode_loopback_fixture", module_path)
            if spec is None or spec.loader is None:
                raise RuntimeError("Loopback fixture module unavailable")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            server = self.stack.enter_context(module.SafariFixture())
            self.environment = {"TEST_RUNNER_ATODE_QA_LOOPBACK_URL": server.url}
            self.record("FIXTURES_READY_NOT_TEST_RESULT", simulator_udid=self.udid, photo=image.name)
            return self
        except BaseException as error:
            self.stack.close()
            screenshot = None
            if stage in {"initialize_photos", "import_synthetic_image"}:
                # Only this already-validated synthetic CI guest is captured.
                # Diagnostic failure must never hide the original setup error.
                screenshot = self.capture_guest()
            self.record("FIXTURE_SETUP_FAILED_NOT_TEST_RESULT", failure_type=type(error).__name__,
                        stage=stage, simulator_screenshot=screenshot)
            raise

    def __exit__(self, *errors):
        try:
            return self.stack.__exit__(*errors)
        finally:
            self.record("FIXTURE_CLOSED_NOT_TEST_RESULT", test_context_failed=errors[0] is not None)

