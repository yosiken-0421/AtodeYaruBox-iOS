"""Synthetic photo and loopback fixtures for the selected CI Simulator only."""
from contextlib import ExitStack
import importlib.util
import json
from pathlib import Path
import platform
import re
import subprocess


class NativeQAFixtures:
    def __init__(self, root, udid):
        self.root = Path(root).resolve()
        self.udid = udid
        self.stack = ExitStack()

    def record(self, status, **details):
        artifacts = self.root / "artifacts"
        artifacts.mkdir(exist_ok=True)
        (artifacts / "external-input-fixtures.json").write_text(json.dumps({
            "status": status, "loopback_only": True, "uses_personal_data": False, **details,
        }, indent=2), encoding="utf-8")

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
                           cwd=self.root, check=True, timeout=60)
            if not image.is_file() or image.stat().st_size == 0:
                raise RuntimeError("Synthetic photo generator did not create the fixture")
            # A newly booted hosted Simulator has not initialized its Photos
            # library yet. Start the stock app on this selected guest only.
            stage = "initialize_photos"
            subprocess.run(["xcrun", "simctl", "launch", self.udid, "com.apple.mobileslideshow"],
                           cwd=self.root, check=True, timeout=60)
            stage = "import_synthetic_image"
            subprocess.run(["xcrun", "simctl", "addmedia", self.udid, str(image)],
                           cwd=self.root, check=True, timeout=180)
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
            self.record("FIXTURE_SETUP_FAILED_NOT_TEST_RESULT", failure_type=type(error).__name__, stage=stage)
            raise

    def __exit__(self, *errors):
        try:
            return self.stack.__exit__(*errors)
        finally:
            self.record("FIXTURE_CLOSED_NOT_TEST_RESULT", test_context_failed=errors[0] is not None)

