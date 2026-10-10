"""GET-only reader for this task's one private signed-package result."""
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.parse
import urllib.request

from tools.codemagic_read_access import APP_ID, NoRedirect, write_report
from tools.codemagic_apple_evidence import DIAGNOSTICS as APPLE_DIAGNOSTICS

BUILD = '6ac9f0fe59e0a0dce2782c3f'
COMMIT = 'a220cf3030f582c581e8e1a514e1c48d37656d10'
BRANCH = 'codex/provisioning-inventory-1f6e311'
NATIVE = '300dc7f7143c3c9e6fc0615effe70bd10efb6950'
NAME = 'signed-package-result.json'
STEP = 'Prepare the private signed package without uploading'
REPORT = Path('artifacts/codemagic-signed-evidence.json')
IDS = ('jp.atodeyarubox.app', 'jp.atodeyarubox.app.share', 'jp.atodeyarubox.app.widgets')
BOOLS = ('signed_archive_verified', 'signed_ipa_verified', 'apple_resources_modified',
         'binary_uploaded', 'billing_modified', 'private_key_disclosed', 'native_tests_repeated',
         'all_three_bundle_ids_available', 'distribution_certificate_created',
         'matching_certificate_key_verified', 'team_identifier_verified')
STAGES = {'preflight', 'inventory', 'BUNDLE_ID_POST_RESERVED', 'CERTIFICATE_POST_RESERVED', 'AUTOMATIC_SIGNING_RESERVED',
          'keychain_create', 'keychain_settings', 'keychain_unlock', 'keychain_read', 'keychain_search',
          'keychain_import', 'keychain_partition', 'archive', 'signature_verify', 'profile_decode',
          'entitlements_read', 'export', 'complete'}
DIAGNOSTICS = APPLE_DIAGNOSTICS | {
    'MACOS_REQUIRED', 'UNAPPROVED_RESOURCE_REQUEST', 'RESOURCE_RESPONSE_LIMIT',
    'RESOURCE_REQUEST_OUTCOME_UNAVAILABLE', 'BUNDLE_CREATION_OUTCOME_UNVERIFIED',
    'CERTIFICATE_KEY_INVALID', 'CERTIFICATE_CONTENT_UNVERIFIED', 'MATCHING_CERTIFICATE_AMBIGUOUS',
    'DISTRIBUTION_CERTIFICATE_LIMIT_NO_REVOCATION', 'CERTIFICATE_CREATION_OUTCOME_UNVERIFIED',
    'MATCHING_CERTIFICATE_EXPIRED', 'CERTIFICATE_TEAM_UNVERIFIED', 'TEAM_IDENTIFIER_INVALID',
    'PROFILE_ID_TEAM_OR_GROUP_MISMATCH', 'PROFILE_NOT_APP_STORE_DISTRIBUTION', 'PROFILE_EXPIRED_OR_UNVERIFIED',
    'APP_GROUP_REGISTRATION_REQUIRED', 'PROFILE_APP_GROUP_SETUP_REQUIRED', 'DEVELOPMENT_PROFILE_DEVICE_REQUIRED',
    'APPLE_ACCOUNT_REQUIRED', 'PROVISIONING_SETTINGS_CONFLICT', 'SIGNING_PERMISSION_REQUIRED', 'SIGNED_BUILD_FAILED',
    'SIGNED_PRODUCT_METADATA_MISSING', 'SIGNED_PRODUCT_ID_OR_PRIVACY_MISMATCH', 'PROFILE_CONTENT_INVALID',
    'SIGNED_ENTITLEMENTS_INVALID', 'SIGNED_ENTITLEMENTS_PROFILE_MISMATCH', 'COMMAND_TIMEOUT', 'COMMAND_UNAVAILABLE',
    'COMMAND_FAILED', 'PKCS12_COMPATIBILITY_REQUIRED', 'SIGNED_IPA_NOT_UNIQUE', 'SIGNED_IPA_SIZE_REFUSED', 'SIGNED_IPA_PATH_REFUSED',
    'UNEXPECTED_SIGNED_PACKAGE_FAILURE', 'INVENTORY_IDENTIFIER_MAP_INVALID', 'INVENTORY_ROUTE_REFUSED',
    'INVENTORY_RESPONSE_LIMIT', 'INVENTORY_READ_UNAVAILABLE', 'INVENTORY_PROFILE_DECODE_UNVERIFIED',
    'INVENTORY_TASK_IDENTIFIER_MISSING', 'UNAPPROVED_SIGNING_MODE'}


def sanitize(payload):
    if (not isinstance(payload, dict) or not isinstance(payload.get('status'), str)
            or payload.get('status') not in {'NOT_RUN', 'NOT_VERIFIED', 'SIGNED_PACKAGE_VERIFIED', 'SIGNING_INVENTORY_READ'}
            or payload.get('verified_native_source') != NATIVE or not isinstance(payload.get('stage'), str)
            or payload.get('stage') not in STAGES):
        return None
    if any(payload.get(k) is not False for k in ('binary_uploaded', 'billing_modified', 'private_key_disclosed', 'native_tests_repeated')):
        return None
    result = {k: payload[k] for k in ('status', 'verified_native_source', 'stage')}
    for key in BOOLS:
        if key in payload:
            if type(payload[key]) is not bool:
                return None
            result[key] = payload[key]
    if any(type(payload.get(k)) is not bool for k in BOOLS[:7]):
        return None
    if 'diagnostic' in payload:
        value = payload['diagnostic']
        if not isinstance(value, str) or value not in DIAGNOSTICS and not re.fullmatch(r'(?:APPLE|RESOURCE)_HTTP_[1-5][0-9]{2}', value):
            return None
        result['diagnostic'] = value
    for key in ('compile_errors', 'compiler_warnings'):
        if key in payload:
            if type(payload[key]) is not int or not 0 <= payload[key] <= 10000:
                return None
            result[key] = payload[key]
    if 'bundle_ids_created' in payload:
        created = payload['bundle_ids_created']
        if (not isinstance(created, list) or any(type(i) is not str or i not in IDS for i in created)
                or len(created) != len(set(created))):
            return None
        result['bundle_ids_created'] = created
    if payload['status'] == 'SIGNED_PACKAGE_VERIFIED':
        if (any(payload.get(k) is not True for k in ('signed_archive_verified', 'signed_ipa_verified',
                'all_three_bundle_ids_available', 'matching_certificate_key_verified', 'team_identifier_verified'))
                or payload['stage'] != 'complete' or 'diagnostic' in payload
                or not isinstance(payload.get('ipa_sha256'), str) or not re.fullmatch(r'[0-9a-f]{64}', payload['ipa_sha256'])
                or type(payload.get('ipa_size_bytes')) is not int or not 0 < payload['ipa_size_bytes'] <= 500 * 1024 * 1024):
            return None
        result.update(ipa_sha256=payload['ipa_sha256'], ipa_size_bytes=payload['ipa_size_bytes'])
    elif payload['signed_ipa_verified']:
        return None
    if payload['status'] == 'SIGNING_INVENTORY_READ':
        inventory = payload.get('provisioning_inventory')
        fields = {'app_groups_capability_enabled', 'profiles_returned', 'active_profiles_with_exact_group', 'app_store_profiles_with_exact_group'}
        if payload['stage'] != 'inventory' or payload['apple_resources_modified'] is not False or not isinstance(inventory, dict) or set(inventory) != set(IDS):
            return None
        for item in inventory.values():
            if (not isinstance(item, dict) or set(item) != fields or type(item['app_groups_capability_enabled']) is not bool
                    or any(type(item[k]) is not int or not 0 <= item[k] <= 200 for k in fields - {'app_groups_capability_enabled'})
                    or not item['app_store_profiles_with_exact_group'] <= item['active_profiles_with_exact_group'] <= item['profiles_returned']):
                return None
        result['provisioning_inventory'] = inventory
    return result


def classify_log(raw):
    text = raw.decode('utf-8', errors='replace')
    result = {'unit_checks_passed': bool(re.search(r'Ran 43 tests[^\n]*\n\s*\nOK(?:\n|$)', text)),
              'unit_checks_failed': 'FAILED (' in text, 'python_module_missing': 'ModuleNotFoundError' in text}
    decoder = json.JSONDecoder()
    for match in re.finditer(r'\{', text):
        try:
            candidate, _ = decoder.raw_decode(text[match.start():])
        except ValueError:
            continue
        report = sanitize(candidate)
        if report is not None:
            result['signed_report'] = report
    return result


def download_url(url, name=None):
    if not isinstance(url, str) or len(url) > 8192:
        return False
    try:
        p = urllib.parse.urlsplit(url)
        return (p.scheme == 'https' and not p.username and not p.password and p.port in (None, 443)
                and p.hostname in {'api.codemagic.io', 'codemagic.io', 'storage.googleapis.com'}
                and not p.fragment and (name is None or urllib.parse.unquote(p.path).endswith('/' + name)))
    except ValueError:
        return False


def inspect(token, opener=None, storage=None):
    result = dict(status='NOT_VERIFIED', app_id=APP_ID, build_id=BUILD, build_commit=COMMIT,
                  private_key_used=False, resources_modified=False, builds_started=0)
    if not isinstance(token, str) or not re.fullmatch(r'[!-~]{20,4096}', token.strip()):
        return {**result, 'diagnostic': 'TOKEN_INVALID'}
    opener = opener or urllib.request.build_opener(NoRedirect())
    storage = storage or urllib.request.build_opener(NoRedirect())
    def read(url, limit, authenticated):
        request = urllib.request.Request(url, method='GET', headers={'x-auth-token': token.strip()} if authenticated else {})
        with (opener if authenticated else storage).open(request, timeout=15) as response:
            raw = response.read(limit + 1)
        if len(raw) > limit:
            raise ValueError()
        return raw
    try:
        build = json.loads(read('https://codemagic.io/api/v3/builds/' + BUILD, 1024 * 1024, True)).get('data')
        if (not isinstance(build, dict) or build.get('id') != BUILD or build.get('app_id') != APP_ID
                or build.get('branch') != BRANCH or (build.get('commit') or {}).get('hash') != COMMIT):
            return {**result, 'diagnostic': 'BUILD_IDENTITY_UNVERIFIED'}
        if build.get('status') not in {'finished', 'failed', 'canceled', 'timeout', 'skipped'}:
            return {**result, 'diagnostic': 'BUILD_NOT_FINISHED'}
        result['build_status'] = build['status']
        artifacts = build.get('artifacts')
        if not isinstance(artifacts, list) or len(artifacts) > 50:
            return {**result, 'diagnostic': 'ARTIFACT_LIST_UNVERIFIED'}
        reports = [a for a in artifacts if isinstance(a, dict) and a.get('name') == NAME]
        if len(reports) == 1 and download_url(reports[0].get('short_lived_download_url'), NAME):
            report = sanitize(json.loads(read(reports[0]['short_lived_download_url'], 64 * 1024, False)))
            if report is not None:
                return {**result, 'status': 'KNOWN_SIGNED_REPORT_READ', 'signed_report': report}
        data = json.loads(read('https://api.codemagic.io/builds/' + BUILD, 1024 * 1024, True))
        b = data.get('build', {})
        actions = b.get('buildActions', [])
        if (data.get('application', {}).get('_id') != APP_ID or b.get('_id') != BUILD
                or not isinstance(actions, list) or len(actions) < 3):
            return {**result, 'diagnostic': 'LOG_BUILD_IDENTITY_UNVERIFIED'}
        action = actions[2]
        if not isinstance(action, dict) or STEP not in (action.get('name'), action.get('title')):
            return {**result, 'diagnostic': 'LOG_ACTION_IDENTITY_UNVERIFIED'}
        children = action.get('subactions')
        child = children[0] if isinstance(children, list) and children and isinstance(children[0], dict) else {}
        inline = action.get('logs') or child.get('logs')
        if isinstance(inline, str) and len(inline.encode()) <= 256 * 1024:
            classified = classify_log(inline.encode())
        else:
            url = action.get('logUrl') or child.get('logUrl')
            if not download_url(url):
                return {**result, 'diagnostic': 'LOG_URL_REFUSED'}
            classified = classify_log(read(url, 256 * 1024, urllib.parse.urlsplit(url).hostname == 'api.codemagic.io'))
        return {**result, 'status': 'KNOWN_SIGNED_STEP_READ', **classified}
    except urllib.error.HTTPError as error:
        return {**result, 'diagnostic': 'HTTP_' + str(int(error.code))}
    except Exception:
        return {**result, 'diagnostic': 'REQUEST_UNAVAILABLE'}


def main():
    write_report(REPORT, {'status': 'NOT_RUN', 'app_id': APP_ID})
    result = inspect(os.environ.pop('CODEMAGIC_API_TOKEN', ''))
    source = os.environ.get('GITHUB_SHA', '')
    if re.fullmatch(r'[0-9a-f]{40}', source):
        result['source_commit'] = source
    write_report(REPORT, result)
    print(result['status'])
    return 0 if result['status'] in {'KNOWN_SIGNED_REPORT_READ', 'KNOWN_SIGNED_STEP_READ'} else 1


if __name__ == '__main__':
    raise SystemExit(main())
