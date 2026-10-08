"""Export actual Simulator test attachments for private review, without changing XCTest results."""
import json
from pathlib import Path
import platform
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    artifacts = ROOT / "artifacts"
    artifacts.mkdir(exist_ok=True)
    report = {"status": "NOT_RUN", "screenshots": [], "reason": "Execution in progress"}
    status_path = artifacts / "ui-attachments-result.json"
    status_path.write_text(json.dumps(report), encoding="utf-8")
    try:
        result = json.loads((artifacts / "ios-build-result.json").read_text(encoding="utf-8"))
        bundle = result.get("result_bundle") or ""
        if not re.fullmatch(r"Tests-\d{8}-\d{6}-[0-9a-f]{8}\.xcresult", bundle):
            raise ValueError("No actual XCTest result bundle recorded")
        source = artifacts / bundle
        if not source.is_dir() or source.is_symlink() or not source.resolve().is_relative_to(artifacts.resolve()):
            raise ValueError("Actual XCTest result bundle unavailable")
        if platform.system() != "Darwin" or not shutil.which("xcrun"):
            raise ValueError("Xcode attachment exporter unavailable on this host")
        destination = artifacts / ("UI-" + bundle.removesuffix(".xcresult"))
        with (artifacts / "ui-attachments-export.log").open("w", encoding="utf-8") as log:
            process = subprocess.run(["xcrun", "xcresulttool", "export", "attachments", "--path", str(source),
                "--output-path", str(destination)], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=120)
        if process.returncode:
            raise ValueError("Xcode attachment export failed; see private export log")
        images = [path.relative_to(artifacts).as_posix() for path in destination.rglob("*.png") if path.is_file()]
        report.update(status="PASS" if images else "FAIL", screenshots=sorted(images),
                      reason="Actual XCTest PNG attachments exported" if images else "No PNG attachments found")
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        report.update(status="FAIL", reason=str(error))
    status_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
