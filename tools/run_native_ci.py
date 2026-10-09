"""Always produce the XCTest report, while preserving the real build/test failure."""
import argparse
import json
if __package__:
    from .build_mac import main as build, ROOT
    from .verify_native_result import inspect, junit
else:
    from build_mac import main as build, ROOT
    from verify_native_result import inspect, junit


def main(scope="all", simulator_signing=False, external_input_qa=False):
    result = build(scope, simulator_signing=simulator_signing, external_input_qa=external_input_qa)
    try:
        report = inspect(ROOT, 76, 10)
        (ROOT / "artifacts/native-acceptance.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        junit(report, ROOT / "artifacts/native-tests.xml")
    except (OSError, ValueError, TypeError) as error:
        print("XCTest report could not be produced: " + str(error))
        return result or 1
    return result or (0 if report["status"] == "PASS" else 1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", choices=["all", "unit"], default="all")
    parser.add_argument("--simulator-signing", action="store_true")
    parser.add_argument("--external-input-qa", action="store_true")
    args = parser.parse_args()
    raise SystemExit(main(args.scope, args.simulator_signing, args.external_input_qa))
