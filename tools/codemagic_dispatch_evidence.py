"""GET-only diagnostic for the one already requested owner upload webhook."""
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.request
from tools.codemagic_read_access import APP_ID, NoRedirect, write_report

BRANCH = 'codex/owner-testflight-cc30610'
COMMIT = '40af4c84d488e0fb787780bdaab57aeab7872b2f'
URL = 'https://api.codemagic.io/apps/' + APP_ID + '/webhooks'
REPORT = Path('artifacts/codemagic-dispatch-evidence.json')
FIELDS = {'webhooks', 'results', 'result', 'request', 'response', 'payload', 'body', 'data', 'message',
          'startedBuilds', 'cancelledBuilds', 'skippedWorkflows', 'branch', 'commitHash', 'commit', 'ref', 'sha',
          'status', 'headers', 'event', 'createdAt', 'timestamp', 'id', '_id'}


def classify(payload):
    candidates, visited = [], 0
    def walk(value, depth=0):
        nonlocal visited
        visited += 1
        if depth > 8 or visited > 3000:
            return
        if isinstance(value, dict):
            serialized = json.dumps(value)
            if BRANCH in serialized and COMMIT in serialized and ('results' in value or 'result' in value):
                candidates.append(value)
            for entry in value.values():
                if isinstance(entry, (dict, list)):
                    walk(entry, depth+1)
        elif isinstance(value, list):
            for entry in value[:100]:
                walk(entry, depth+1)
    walk(payload)
    result = dict(matching_dispatch_found=bool(candidates), started_build_ids=[], reason_codes=[],
                  response_type='OBJECT' if isinstance(payload, dict) else 'ARRAY' if isinstance(payload, list) else 'OTHER')
    if not candidates:
        result['top_level_fields'] = sorted(set(payload) & FIELDS) if isinstance(payload, dict) else []
        if isinstance(payload, list) and payload and isinstance(payload[0], dict):
            result['first_record_fields'] = sorted(set(payload[0]) & FIELDS)
        return result
    entry = min(candidates, key=lambda value: len(json.dumps(value)))
    result['matched_record_fields'] = sorted(set(entry) & FIELDS)
    data = entry.get('results', entry.get('result'))
    if isinstance(data, dict):
        started = data.get('startedBuilds', [])
        if isinstance(started, list):
            result['started_build_ids'] = [row['id'] for row in started[:10] if isinstance(row, dict)
                and row.get('appId') == APP_ID and isinstance(row.get('id'), str)
                and re.fullmatch('[0-9a-f]{24}', row['id'])]
        skipped = data.get('skippedWorkflows', [])
        if isinstance(skipped, list):
            result['skipped_workflow_count'] = min(len(skipped), 100)
    text = json.dumps(data).lower()
    patterns = {
        'CONFIGURATION_REJECTED': r'validat|configuration|yaml.*error|error.*yaml|invalid.*(?:publish|config)',
        'PUBLISHING_CONFIGURATION_REJECTED': r'publish|app.store.connect',
        'INTEGRATION_REFERENCE_REJECTED': r'integration|alias',
        'SUBSCRIPTION_OR_BUDGET_REJECTED': r'subscription|billing|free.*limit|minute.*limit',
        'TRIGGER_DID_NOT_MATCH': r'no.*workflow|branch.*match|skip.*workflow',
        'PROVIDER_ERROR': r'error|failed|invalid|reject',
    }
    result['reason_codes'] = sorted(name for name, pattern in patterns.items() if re.search(pattern, text))
    result['referenced_configuration_fields'] = sorted(name for name in (
        'auth', 'publishing', 'app_store_connect', 'submit_to_testflight', 'submit_to_app_store', 'integrations',
        'ASC_KEY_ALIAS', 'environment', 'max_build_duration') if name.lower() in text)
    return result


def inspect(token, opener=None):
    result = dict(status='NOT_VERIFIED', app_id=APP_ID, branch=BRANCH, build_commit=COMMIT,
        private_key_used=False, resources_modified=False, builds_started=0)
    if not isinstance(token, str) or not re.fullmatch(r'[!-~]{20,4096}', token.strip()):
        return result | {'diagnostic': 'TOKEN_INVALID'}
    opener = opener or urllib.request.build_opener(NoRedirect())
    try:
        request = urllib.request.Request(URL, method='GET', headers={'x-auth-token': token.strip()})
        with opener.open(request, timeout=20) as response:
            raw = response.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            return result | {'diagnostic': 'RESPONSE_LIMIT'}
        return result | {'status': 'KNOWN_WEBHOOK_DISPATCH_READ', 'dispatch': classify(json.loads(raw))}
    except urllib.error.HTTPError as error:
        return result | {'diagnostic': 'HTTP_' + str(int(error.code))}
    except Exception:
        return result | {'diagnostic': 'REQUEST_UNAVAILABLE'}


def main():
    write_report(REPORT, {'status': 'NOT_RUN', 'app_id': APP_ID})
    result = inspect(os.environ.pop('CODEMAGIC_API_TOKEN', ''))
    result['source_commit'] = os.environ.get('GITHUB_SHA', '')
    write_report(REPORT, result)
    print(result['status'])
    return 0 if result['status'] == 'KNOWN_WEBHOOK_DISPATCH_READ' else 1

if __name__ == '__main__':
    raise SystemExit(main())
