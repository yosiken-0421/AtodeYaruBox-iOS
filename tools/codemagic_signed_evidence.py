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

BUILD = '6acae6112e8bb15cf3ab22fb'
COMMIT = '334125507a6927fdcc25bdcd4d2e74f340a17b5b'
BRANCH = 'codex/owner-testflight-tester-alternate-d5b63c5'
NATIVE = '300dc7f7143c3c9e6fc0615effe70bd10efb6950'
NAME = 'signed-package-result.json'
STEP = 'Prepare the private signed package without uploading'
REPORT = Path('artifacts/codemagic-signed-evidence.json')
IDS = ('jp.atodeyarubox.app', 'jp.atodeyarubox.app.share', 'jp.atodeyarubox.app.widgets')
BOOLS = ('signed_archive_verified', 'signed_ipa_verified', 'apple_resources_modified',
         'binary_uploaded', 'billing_modified', 'private_key_disclosed', 'native_tests_repeated',
         'all_three_bundle_ids_available', 'distribution_certificate_created',
         'matching_certificate_key_verified', 'team_identifier_verified')
STAGES = {'preflight', 'app_record', 'testflight_read', 'inventory', 'profile_prepare', 'profile_install', 'MANUAL_SIGNING_PREPARED', 'BUNDLE_ID_POST_RESERVED', 'CERTIFICATE_POST_RESERVED', 'AUTOMATIC_SIGNING_RESERVED',
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
    'INVENTORY_TASK_IDENTIFIER_MISSING', 'UNAPPROVED_SIGNING_MODE', 'EXISTING_SIGNING_RESOURCES_REQUIRED',
    'PROFILE_RESOURCE_ID_UNVERIFIED', 'PROFILE_ROUTE_REFUSED', 'PROFILE_ROUTE_OR_REPLAY_REFUSED',
    'PROFILE_RESPONSE_LIMIT', 'PROFILE_CREATION_OUTCOME_UNVERIFIED', 'PROFILE_REQUEST_OUTCOME_UNAVAILABLE',
    'APP_GROUP_PROFILE_ASSIGNMENT_REQUIRED', 'PROFILE_CERTIFICATE_MISMATCH', 'PROFILE_OWNED_MATCH_AMBIGUOUS',
    'PROFILE_PREPARATION_UNAVAILABLE', 'PROFILE_NAME_OR_UUID_UNVERIFIED', 'PROFILE_INSTALL_COLLISION',
    'MANUAL_SIGNING_MATERIAL_UNVERIFIED', 'MANUAL_SIGNING_TARGET_MISMATCH',
    'APP_RECORD_RESPONSE_LIMIT', 'APP_RECORD_IDENTITY_UNVERIFIED', 'APP_RECORD_READ_UNAVAILABLE',
    'TESTFLIGHT_RESPONSE_UNVERIFIED', 'TESTFLIGHT_BUILD_IDENTITY_MISMATCH', 'TESTFLIGHT_AUDIENCE_NOT_INTERNAL',
    'TESTFLIGHT_VALID_BUILD_METADATA_UNVERIFIED', 'TESTFLIGHT_RESPONSE_LIMIT', 'TESTFLIGHT_READ_UNAVAILABLE'}


def sanitize(payload):
    if isinstance(payload, dict) and payload.get('status') == 'OWNER_INTERNAL_TESTFLIGHT_TESTER_REGISTERED':
        required=('owner_email_matches','owner_tester_registered','owner_internal_group_verified','owner_internal_build_assigned')
        disabled=('public_link_enabled','automatic_future_builds','binary_uploaded','billing_modified','private_key_disclosed')
        if (payload.get('app_record_id') != '6821479152' or payload.get('apple_build_id') != '3dc8936a-6059-4ad2-b8c1-9ffcc555a7ea'
                or payload.get('group_id') != 'b170086a-49ff-4990-b9cc-b68df67cd5df'
                or not isinstance(payload.get('tester_id'),str) or not re.fullmatch('[0-9a-fA-F]{8}(-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}',payload['tester_id'])
                or any(payload.get(k) is not True for k in required) or any(payload.get(k) is not False for k in disabled)
                or type(payload.get('owner_testers_registered')) is not int or payload['owner_testers_registered'] != 1
                or type(payload.get('other_testers_invited')) is not int or payload['other_testers_invited'] != 0
                or type(payload.get('apple_resources_modified')) is not bool
                or payload.get('tester_state') not in {'INVITED','ACCEPTED','INSTALLED','NOT_INVITED','REVOKED','UNKNOWN'}):
            return None
        keys=('status','app_record_id','apple_build_id','group_id','tester_id','tester_state','owner_testers_registered','other_testers_invited','apple_resources_modified')+required+disabled
        return {k:payload[k] for k in keys}
    if isinstance(payload, dict) and payload.get('status') == 'OWNER_TESTFLIGHT_GROUP_STATE_READ':
        if (payload.get('app_record_id') != '6821479152' or payload.get('apple_build_id') != '3dc8936a-6059-4ad2-b8c1-9ffcc555a7ea'
                or type(payload.get('group_count')) is not int or not 0 <= payload['group_count'] <= 1
                or any(payload.get(k) is not False for k in ('apple_resources_modified','binary_uploaded','billing_modified','private_key_disclosed'))
                or type(payload.get('testers_invited')) is not int or payload['testers_invited'] != 0):
            return None
        result={k:payload[k] for k in ('status','app_record_id','apple_build_id','group_count','apple_resources_modified','binary_uploaded','billing_modified','private_key_disclosed','testers_invited')}
        for key in ('resource_type_matches','group_name_matches','group_id_is_uuid','app_relationship_matches','app_bundle_matches','accepted_internal_build_matches','build_relationship_present','exact_build_relationship_matches'):
            if key in payload:
                if type(payload[key]) is not bool:return None
                result[key]=payload[key]
        for key in ('isInternalGroup','publicLinkEnabled','hasAccessToAllBuilds'):
            if key in payload:
                if payload[key] is not None and type(payload[key]) is not bool and payload[key] != 'OTHER':return None
                result[key]=payload[key]
        if 'group_id' in payload:
            if not isinstance(payload['group_id'],str) or not re.fullmatch('[0-9a-fA-F-]{36}',payload['group_id']):return None
            result['group_id']=payload['group_id']
        if 'build_count' in payload:
            if type(payload['build_count']) is not int or not 0 <= payload['build_count'] <= 2:return None
            result['build_count']=payload['build_count']
        if 'attribute_fields_present' in payload:
            fields=payload['attribute_fields_present']
            if not isinstance(fields,list) or not set(fields).issubset({'name','isInternalGroup','publicLinkEnabled','hasAccessToAllBuilds'}):return None
            result['attribute_fields_present']=fields
        return result
    if isinstance(payload, dict) and payload.get('status') == 'OWNER_INTERNAL_TESTFLIGHT_GROUP_READY':
        if (payload.get('app_record_id') != '6821479152'
                or payload.get('apple_build_id') != '3dc8936a-6059-4ad2-b8c1-9ffcc555a7ea'
                or not isinstance(payload.get('group_id'), str) or not re.fullmatch('[0-9a-fA-F-]{36}', payload['group_id'])
                or payload.get('owner_internal_group_verified') is not True or payload.get('owner_internal_build_assigned') is not True
                or any(payload.get(k) is not False for k in ('public_link_enabled', 'automatic_future_builds', 'binary_uploaded', 'billing_modified', 'private_key_disclosed'))
                or type(payload.get('apple_resources_modified')) is not bool or type(payload.get('testers_invited')) is not int or payload['testers_invited'] != 0):
            return None
        return {k: payload[k] for k in ('status', 'app_record_id', 'apple_build_id', 'group_id',
            'owner_internal_group_verified', 'owner_internal_build_assigned', 'public_link_enabled',
            'automatic_future_builds', 'testers_invited', 'apple_resources_modified', 'binary_uploaded', 'billing_modified', 'private_key_disclosed')}
    if (not isinstance(payload, dict) or not isinstance(payload.get('status'), str)
            or payload.get('status') not in {'NOT_RUN', 'NOT_VERIFIED', 'APPLE_TESTFLIGHT_BUILD_PENDING', 'APPLE_TESTFLIGHT_BUILD_READ', 'APP_RECORD_READ', 'SIGNED_PACKAGE_VERIFIED', 'SIGNING_INVENTORY_READ', 'DISTRIBUTION_PROFILES_VERIFIED'}
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
    if payload['stage'] == 'testflight_read':
        if (payload.get('app_record_id') != '6821479152' or payload['apple_resources_modified'] is not False
                or payload['signed_archive_verified'] is not False or payload['signed_ipa_verified'] is not False
                or any(type(payload.get(k)) is not bool for k in ('app_store_binary_present', 'eligible_internal_testing'))):
            return None
        result.update(app_record_id='6821479152', app_store_binary_present=payload['app_store_binary_present'],
            eligible_internal_testing=payload['eligible_internal_testing'])
        for key in ('internal_testing_only', 'metadata_verified', 'uses_non_exempt_encryption', 'public_group_link_present'):
            if key in payload:
                if type(payload[key]) is not bool:
                    return None
                result[key] = payload[key]
        for key, values in {'processing_state': {'PROCESSING', 'FAILED', 'INVALID', 'VALID'},
            'internal_beta_state': {'PROCESSING', 'PROCESSING_EXCEPTION', 'MISSING_EXPORT_COMPLIANCE', 'READY_FOR_BETA_TESTING', 'IN_BETA_TESTING', 'EXPIRED', 'IN_EXPORT_COMPLIANCE_REVIEW'},
            'version': {'0.1.0'}, 'platform': {'IOS'}, 'build_number': {'1'}}.items():
            if key in payload:
                if payload[key] not in values:
                    return None
                result[key] = payload[key]
        for key, limit in (('internal_group_count', 50), ('read_attempts', 6)):
            if key in payload:
                if type(payload[key]) is not int or not 0 <= payload[key] <= limit:
                    return None
                result[key] = payload[key]
        if 'apple_build_id' in payload:
            if not isinstance(payload['apple_build_id'], str) or not re.fullmatch('[0-9a-fA-F-]{36}', payload['apple_build_id']):
                return None
            result['apple_build_id'] = payload['apple_build_id']
        if payload['status'] == 'APPLE_TESTFLIGHT_BUILD_READ' and (payload['app_store_binary_present'] is not True or 'apple_build_id' not in result):
            return None
        if payload['status'] == 'APPLE_TESTFLIGHT_BUILD_PENDING' and payload['app_store_binary_present'] is not False:
            return None
        if payload['eligible_internal_testing'] and (payload['status'] != 'APPLE_TESTFLIGHT_BUILD_READ'
                or payload.get('processing_state') != 'VALID' or payload.get('internal_testing_only') is not True
                or payload.get('metadata_verified') is not True or payload.get('version') != '0.1.0'
                or payload.get('platform') != 'IOS' or payload.get('uses_non_exempt_encryption') is not False
                or payload.get('internal_beta_state') not in {'READY_FOR_BETA_TESTING', 'IN_BETA_TESTING'}):
            return None
    elif payload['status'].startswith('APPLE_TESTFLIGHT_'):
        return None
    if payload['status'] == 'APP_RECORD_READ':
        if (payload['stage'] != 'app_record' or payload.get('app_record_read_verified') is not True
                or type(payload.get('app_record_exists')) is not bool or payload['apple_resources_modified'] is not False):
            return None
        result.update(app_record_read_verified=True, app_record_exists=payload['app_record_exists'])
        if payload['app_record_exists']:
            if not isinstance(payload.get('app_record_id'), str) or not re.fullmatch(r'[0-9]{6,12}', payload['app_record_id']):
                return None
            result['app_record_id'] = payload['app_record_id']
        elif 'app_record_id' in payload:
            return None
    for key in ('compile_errors', 'compiler_warnings'):
        if key in payload:
            if type(payload[key]) is not int or not 0 <= payload[key] <= 10000:
                return None
            result[key] = payload[key]
    if 'inventory_failure' in payload:
        from tools.apple_provisioning_inventory import ERROR_CODES, PARAMETERS
        failure = payload['inventory_failure']
        if (payload['stage'] != 'inventory' or payload['status'] != 'NOT_VERIFIED'
                or payload['apple_resources_modified'] is not False or not isinstance(failure, dict)
                or set(failure) != {'relationship', 'apple_error_code', 'parameter'}
                or failure.get('relationship') not in ('bundleIds', 'bundleIdCapabilities', 'profiles')
                or not isinstance(failure.get('apple_error_code'), str) or failure['apple_error_code'] not in ERROR_CODES
                or not isinstance(failure.get('parameter'), str) or failure['parameter'] not in PARAMETERS):
            return None
        result['inventory_failure'] = failure
    for key in ('profiles_created_count', 'verified_distribution_profiles'):
        if key in payload:
            if type(payload[key]) is not int or not 0 <= payload[key] <= 3:
                return None
            result[key] = payload[key]
    if 'distribution_profiles_verified' in payload:
        if type(payload['distribution_profiles_verified']) is not bool:
            return None
        result['distribution_profiles_verified'] = payload['distribution_profiles_verified']
    if payload['status'] == 'DISTRIBUTION_PROFILES_VERIFIED' and (payload['stage'] != 'profile_prepare'
            or payload.get('distribution_profiles_verified') is not True or payload.get('verified_distribution_profiles') != 3):
        return None
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
    result = {'unit_checks_passed': bool(re.search(r'Ran 47 tests[^\n]*\n\s*\nOK(?:\n|$)', text)),
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
        if (isinstance(candidate, dict) and candidate.get('status') == 'NOT_VERIFIED'
                and candidate.get('testers_invited') == 0 and candidate.get('binary_uploaded') is False
                and candidate.get('billing_modified') is False and candidate.get('private_key_disclosed') is False):
            code = candidate.get('diagnostic')
            if isinstance(code, str) and (code in {'OWNER_GROUP_ROUTE_REFUSED', 'OWNER_GROUP_BODY_OR_REPLAY_REFUSED',
                    'OWNER_GROUP_RESPONSE_LIMIT', 'OWNER_GROUP_OUTCOME_UNAVAILABLE', 'OWNER_GROUP_RESPONSE_UNVERIFIED',
                    'OWNER_GROUP_IDENTITY_UNVERIFIED', 'OWNER_GROUP_APP_UNVERIFIED', 'OWNER_GROUP_BUILD_UNVERIFIED', 'OWNER_GROUP_ASSIGNMENT_UNVERIFIED',
                    'OWNER_TESTER_ROUTE_REFUSED','OWNER_TESTER_BODY_OR_REPLAY_REFUSED','OWNER_TESTER_RESPONSE_LIMIT',
                    'OWNER_TESTER_OUTCOME_UNAVAILABLE','OWNER_TESTER_GROUP_UNVERIFIED','OWNER_TESTER_RESPONSE_UNVERIFIED',
                    'OWNER_TESTER_IDENTITY_UNVERIFIED','OWNER_TESTER_MEMBERSHIP_UNVERIFIED'}
                    or re.fullmatch('APPLE_HTTP_[1-5][0-9]{2}', code)):
                result['owner_group_diagnostic'] = code
            if candidate.get('owner_tester_stage') in {'group_read','tester_read','existing_owner_read','tester_create','group_assign','tester_verify','group_verify'}:
                result['owner_tester_stage']=candidate['owner_tester_stage']
            for key in ('tester_rows_are_list','tester_lookup_has_next','apple_error_mentions_app_mismatch','apple_error_mentions_internal'):
                if type(candidate.get(key)) is bool:result[key]=candidate[key]
            count=candidate.get('tester_lookup_count')
            if type(count) is int and 0 <= count <= 2:result['tester_lookup_count']=count
            for key in ('existing_candidate_count','internal_candidate_count','active_internal_candidate_count'):
                count=candidate.get(key)
                if type(count) is int and 0 <= count <= 50:result[key]=count
            categories=candidate.get('apple_error_categories')
            if isinstance(categories,list) and len(categories)<=4 and all(x in {'RELATIONSHIP_INVALID','ATTRIBUTE_EXISTS','ATTRIBUTE_INVALID','CONTRACT_MISSING','OTHER'} for x in categories):
                result['apple_error_categories']=categories
            codes=candidate.get('apple_error_codes')
            if isinstance(codes,list) and len(codes)<=4 and all(isinstance(x,str) and re.fullmatch(r'(ENTITY_ERROR|STATE_ERROR|PARAMETER_ERROR|FORBIDDEN_ERROR|NOT_FOUND|ENTITY_UNPROCESSABLE)(\.[A-Z_0-9]{1,60}){0,3}',x) for x in codes):
                result['apple_error_codes']=codes
            summary=candidate.get('apple_error_summary')
            if isinstance(summary,str) and re.fullmatch(r'[A-Za-z .,:;()/\-]{1,300}',summary) and not any(x in summary.lower() for x in ('bearer','private key','begin ec','begin rsa')):
                result['apple_error_summary']=summary
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
