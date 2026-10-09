"""Verification of a fresh native Release Simulator build; not device distribution."""
from datetime import datetime, timezone
import json
from pathlib import Path
import re

def inspect(root, now=None):
    now = now or datetime.now(timezone.utc)
    raw = json.loads((root / 'artifacts/ios-release-build-result.json').read_text(encoding='utf-8'))
    problems = []
    if raw.get('configuration') != 'Release' or raw.get('scope') != 'build':
        problems.append('Not a Release-only build')
    if raw.get('build') != 'PASS' or raw.get('build_exit_code') != 0 or raw.get('errors'):
        problems.append('Native Release build failed or recorded errors')
    if raw.get('tests') != 'NOT_RUN':
        problems.append('Release build must not replace the separate complete XCTest evidence')
    try:
        started = datetime.fromisoformat(raw['started_at'])
        finished = datetime.fromisoformat(raw['finished_at'])
        if started.tzinfo is None or finished.tzinfo is None or not started <= finished <= now or (now - finished).total_seconds() > 3600:
            problems.append('Invalid or stale native Release timestamps')
    except (KeyError, ValueError, TypeError):
        problems.append('Missing native Release timestamps')
    if not raw.get('logs'):
        problems.append('Missing native Release logs')
    for name in raw.get('logs', []):
        if not isinstance(name,str) or Path(name).name != name or not name.endswith('.log'):
            problems.append('Unsafe Release log path')
            continue
        log = root / 'artifacts' / name
        if not log.is_file() or log.stat().st_size > 64 * 1024 * 1024:
            problems.append('Missing or oversized Release log')
    warnings = [line for line in raw.get('warnings', [])
        if re.search(r'\.swift:\d+(?::\d+)?:\s*warning:|(?:Swift|clang|ld):\s*warning:',line)]
    if warnings:
        problems.append('Swift/compiler warnings must be fixed')
    products = root / 'DerivedDataRelease/Build/Products/Release-iphonesimulator'
    app = products / 'AtodeYaruBox.app'
    for path in [app/'AtodeYaruBox', app/'Info.plist', app/'PrivacyInfo.xcprivacy',
        app/'PlugIns/BoxShare.appex/Info.plist', app/'PlugIns/BoxWidgets.appex/Info.plist']:
        if not path.is_file():
            problems.append('Missing built Release product: ' + str(path.relative_to(root)))
    return {'status':'PASS' if not problems else 'FAIL','native_release_only':not problems,
        'problems':problems,'compiler_warnings':warnings,'device_distribution_verified':False}

if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    destination = root / 'artifacts/release-acceptance.json'
    destination.write_text('{"status":"NOT_VERIFIED"}',encoding='utf-8')
    try:
        report = inspect(root)
        destination.write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(report))
        raise SystemExit(report['status'] != 'PASS')
    except (OSError,ValueError,TypeError) as error:
        print('Native Release evidence rejected: ' + str(error))
        raise SystemExit(1)
