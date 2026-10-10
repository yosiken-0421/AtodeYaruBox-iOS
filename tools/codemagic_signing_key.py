"""Create a task-owned RSA key only inside encrypted app-local CI variables."""
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.request

from tools.codemagic_alias_variable import single_page
from tools.codemagic_integration_read import inspect, valid_id
from tools.codemagic_read_access import APP_ID, NoRedirect, RefusedRedirect, write_report

GROUP = 'atodeyarubox-signing-key-d43f7c2'
NAME = 'CERTIFICATE_PRIVATE_KEY'
APP_PATH = '/apps/' + APP_ID + '/variable-groups'
BASE = 'https://codemagic.io/api/v3'
REPORT = Path('artifacts/codemagic-signing-key.json')
LIMIT = 256 * 1024


class Halt(Exception):
    pass


def make_key():
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                             serialization.NoEncryption()).decode('ascii')


def configure(token, opener=None, gate=None, checkpoint=None, factory=make_key):
    result = dict(status='NOT_CONFIGURED', app_id=APP_ID, group_name=GROUP, variable_name=NAME,
                  key_generated=False, encrypted_variable_verified=False,
                  private_key_disclosed=False, apple_resources_modified=False,
                  billing_modified=False, builds_started=0, group_created=False)
    opener = opener or urllib.request.build_opener(NoRedirect())
    gate = gate if gate is not None else inspect(token, opener)
    if (gate.get('status') != 'APP_INTEGRATION_METADATA_READ'
            or gate.get('app_owner_verified') is not True or gate.get('personal_context_owns_app') is not True
            or gate.get('free_allowance_verified') is not True
            or gate.get('paid_cicd_subscription_present') is not False
            or gate.get('free_m2_remaining_seconds', 0) < 1800
            or gate.get('expected_alias_normalized') is not True
            or gate.get('expected_alias_ambiguous') is not False):
        return {**result, 'status': 'CURRENT_OWNER_ALIAS_AND_FREE_ALLOWANCE_REQUIRED'}
    if not isinstance(token, str) or not re.fullmatch(r'[!-~]{20,4096}', token.strip()):
        return {**result, 'status': 'TOKEN_INVALID'}
    result.update(free_allowance_verified=True, paid_cicd_subscription_present=False,
                  free_m2_remaining_seconds=gate['free_m2_remaining_seconds'])
    group_id = None
    private_key = None

    def request(path, method='GET', body=None):
        allowed = path == APP_PATH and (method == 'GET' or method == 'POST' and body == {'name': GROUP})
        if valid_id(group_id) and path == '/variable-groups/' + group_id + '/variables':
            allowed = method == 'GET' or (method == 'POST' and private_key is not None
                and body == {'secure': True, 'variables': [{'name': NAME, 'value': private_key}]})
        if not allowed:
            raise Halt('REQUEST_SCOPE_REFUSED')
        if method == 'POST':
            result['status'] = 'MUTATION_RESERVED_OUTCOME_UNKNOWN'
            if checkpoint:
                checkpoint(dict(result))
        req = urllib.request.Request(BASE + path, method=method,
            data=None if body is None else json.dumps(body).encode(), headers={
                'x-auth-token': token.strip(), 'Content-Type': 'application/json', 'Accept': 'application/json'})
        try:
            with opener.open(req, timeout=15) as response:
                raw = response.read(LIMIT + 1)
            if len(raw) > LIMIT:
                raise Halt('RESPONSE_LIMIT_EXCEEDED')
            payload = json.loads(raw) if raw else {}
            # The bulk-import acknowledgement can be an array; only subsequent
            # GET metadata establishes a stored, encrypted variable.
            if method == 'POST' and private_key is not None:
                return {}
            if not isinstance(payload, dict):
                raise Halt('RESPONSE_UNVERIFIED')
            return payload
        except urllib.error.HTTPError as error:
            raise Halt('HTTP_' + str(int(error.code))) from None
        except (RefusedRedirect, urllib.error.URLError, TimeoutError, OSError, ValueError):
            raise Halt('REQUEST_OUTCOME_UNAVAILABLE') from None

    def verified_variable(payload):
        rows = payload.get('data')
        return (single_page(payload) and len(rows) == 1 and isinstance(rows[0], dict)
                and rows[0].get('name') == NAME and rows[0].get('secure') is True)

    try:
        groups = request(APP_PATH)
        if not single_page(groups) or any(not isinstance(row, dict) for row in groups['data']):
            raise Halt('GROUP_LIST_UNVERIFIED')
        matching = [row for row in groups['data'] if row.get('name') == GROUP]
        if matching:
            if len(matching) != 1 or not valid_id(matching[0].get('id')):
                raise Halt('EXISTING_GROUP_IDENTITY_UNVERIFIED')
            group_id = matching[0]['id']
            if not verified_variable(request('/variable-groups/' + group_id + '/variables')):
                raise Halt('EXISTING_VARIABLE_UNVERIFIED_NO_OVERWRITE')
            return {**result, 'status': 'ENCRYPTED_SIGNING_KEY_METADATA_VERIFIED',
                    'encrypted_variable_verified': True}
        created = request(APP_PATH, 'POST', {'name': GROUP}).get('data', {})
        if not isinstance(created, dict) or created.get('name') != GROUP or not valid_id(created.get('id')):
            raise Halt('GROUP_CREATION_OUTCOME_UNVERIFIED')
        group_id = created['id']
        result['group_created'] = True
        variables_path = '/variable-groups/' + group_id + '/variables'
        empty = request(variables_path)
        if not single_page(empty) or empty.get('data') != []:
            raise Halt('NEW_GROUP_NOT_EMPTY')
        private_key = factory()
        if (not isinstance(private_key, str) or not 256 <= len(private_key) <= 8192
                or not private_key.startswith('-----BEGIN PRIVATE KEY-----\n')
                or not private_key.strip().endswith('\n-----END PRIVATE KEY-----')):
            raise Halt('GENERATED_KEY_FORMAT_INVALID')
        result['key_generated'] = True
        request(variables_path, 'POST', {'secure': True, 'variables': [{'name': NAME, 'value': private_key}]})
        private_key = None
        if not verified_variable(request(variables_path)):
            raise Halt('ENCRYPTED_VARIABLE_METADATA_UNVERIFIED')
        result.update(status='ENCRYPTED_SIGNING_KEY_CONFIGURED', encrypted_variable_verified=True)
        return result
    except Halt as error:
        return {**result, 'status': 'CONFIGURATION_UNAVAILABLE', 'diagnostic': str(error)}
    except Exception:
        return {**result, 'status': 'CONFIGURATION_UNAVAILABLE', 'diagnostic': 'UNEXPECTED_RESPONSE'}
    finally:
        private_key = None


def main():
    write_report(REPORT, {'status': 'NOT_RUN', 'app_id': APP_ID})
    token = os.environ.pop('CODEMAGIC_API_TOKEN', '')
    result = configure(token, checkpoint=lambda r: write_report(REPORT, r))
    token = ''
    source = os.environ.get('GITHUB_SHA', '')
    if re.fullmatch(r'[0-9a-f]{40}', source):
        result['source_commit'] = source
    write_report(REPORT, result)
    print(result['status'])
    return 0 if result['status'] in ('ENCRYPTED_SIGNING_KEY_CONFIGURED', 'ENCRYPTED_SIGNING_KEY_METADATA_VERIFIED') else 1


if __name__ == '__main__':
    raise SystemExit(main())
