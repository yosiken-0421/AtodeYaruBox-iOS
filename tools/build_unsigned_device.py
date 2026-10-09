"""Build and inspect a Release iPhone archive without signing or distribution."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import plistlib
import re
import shutil
import subprocess
import uuid

if __package__:
    from . import build_mac as builder
else:
    import build_mac as builder

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / 'artifacts'


def main():
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:8]
    archive = ARTIFACTS / ('device-' + stamp + '.xcarchive')
    result = {'archive': 'NOT_RUN', 'configuration': 'Release', 'platform': 'iPhoneOS',
        'signed': False, 'iphone_installable': False, 'device_execution_verified': False,
        'started_at': datetime.now(timezone.utc).isoformat(), 'finished_at': None,
        'source_sha': None, 'archive_exit_code': None, 'logs': [], 'errors': [],
        'warnings': [], 'compiler_warnings': [], 'reason': 'Execution in progress'}
    output_path = ARTIFACTS / 'unsigned-device-build.json'
    def record():
        temporary = output_path.with_suffix('.json.tmp')
        temporary.write_text(json.dumps(result, indent=2), encoding='utf-8')
        temporary.replace(output_path)
    record()

    def run(arguments, name):
        log_name = 'device-' + name + '-' + stamp + '.log'
        result['logs'].append(log_name)
        code, text = builder.execute(arguments, log_name)
        result['warnings'].extend(line for line in text.splitlines() if 'warning:' in line)
        result['compiler_warnings'].extend(line for line in text.splitlines()
            if re.search(r'\.swift:\d+(?::\d+)?:\s*warning:|(?:Swift|clang|ld):\s*warning:', line))
        result['errors'].extend(line for line in text.splitlines() if re.search(r'\berror:', line))
        return code, text

    code = 1
    try:
        if platform.system() != 'Darwin' or not shutil.which('xcodebuild'):
            result['reason'] = 'Full Xcode on macOS is required; no native build ran'
            return 2
        source_sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
        if not re.fullmatch(r'[0-9a-f]{40}', source_sha):
            raise ValueError('Missing current source identity')
        if os.environ.get('GITHUB_SHA', source_sha) != source_sha:
            raise ValueError('Native source differs from the workflow source')
        result['source_sha'] = source_sha
        builder.generate()
        if run(['xcodebuild', '-version'], 'xcode-version')[0] != 0:
            raise RuntimeError('Xcode version check failed')
        arguments = ['xcodebuild', '-project', 'AtodeYaruBox.xcodeproj', '-scheme', 'AtodeYaruBox',
            '-configuration', 'Release', '-sdk', 'iphoneos', '-destination', 'generic/platform=iOS',
            '-derivedDataPath', str(ROOT / 'DerivedDataDevice'), '-archivePath', str(archive),
            'CODE_SIGNING_ALLOWED=NO', 'CODE_SIGNING_REQUIRED=NO', 'archive']
        exit_code, log = run(arguments, 'archive')
        result['archive_exit_code'] = exit_code
        result['archive'] = 'FAIL'
        if exit_code != 0 or '** ARCHIVE SUCCEEDED **' not in log:
            raise RuntimeError('Native iPhone archive did not succeed')
        app = archive / 'Products/Applications/AtodeYaruBox.app'
        bundles = [(app, 'AtodeYaruBox', 'jp.atodeyarubox.app'),
            (app / 'PlugIns/BoxShare.appex', 'BoxShare', 'jp.atodeyarubox.app.share'),
            (app / 'PlugIns/BoxWidgets.appex', 'BoxWidgets', 'jp.atodeyarubox.app.widgets')]
        for bundle, executable, identifier in bundles:
            info = plistlib.loads((bundle / 'Info.plist').read_bytes())
            if (info.get('CFBundleIdentifier') != identifier
                    or info.get('CFBundleSupportedPlatforms') != ['iPhoneOS']
                    or info.get('CFBundleExecutable') != executable
                    or not (bundle / 'PrivacyInfo.xcprivacy').is_file()):
                raise ValueError('Missing or mismatched actual iPhone archive bundle: ' + executable)
            if (bundle / 'embedded.mobileprovision').exists() or (bundle / '_CodeSignature').exists():
                raise ValueError('This check must never include a signed distribution package')
            binary = bundle / executable
            architecture_code, architectures = run(['lipo', '-archs', str(binary)], executable + '-architectures')
            if architecture_code != 0 or architectures.split() != ['arm64']:
                raise ValueError('The actual iPhone binary must use arm64: ' + executable)
            signature_code, signature = run(['codesign', '-d', '--verbose=2', str(binary)], executable + '-unsigned')
            if signature_code != 1 or 'not signed at all' not in signature:
                raise ValueError('Could not confirm the archive is unsigned: ' + executable)
        if result['errors'] or result['compiler_warnings']:
            raise RuntimeError('Native archive errors or compiler warnings require repair')
        result['archive'] = 'PASS'
        result['reason'] = 'All three actual Release iPhone bundles verified. Unsigned and not installable.'
        code = 0
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        result['errors'].append(str(error))
        result['reason'] = 'Native unsigned iPhone archive verification failed'
    finally:
        result['finished_at'] = datetime.now(timezone.utc).isoformat()
        record()
        print(json.dumps(result))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
