import io
import json
import unittest
import urllib.error
from tools import codemagic_dispatch_evidence as m

TOKEN = 'synthetic-secret-no-real-credential'
class Transport:
    def __init__(self, payload):
        self.payload, self.requests = payload, []
    def open(self, request, timeout):
        self.requests.append(request)
        if isinstance(self.payload, Exception):
            raise self.payload
        return io.BytesIO(self.payload if isinstance(self.payload, bytes) else json.dumps(self.payload).encode())
def event():
    return dict(request=dict(branch=m.BRANCH, commitHash=m.COMMIT),
                results=dict(startedBuilds=[dict(id='a'*24, appId=m.APP_ID)], message=TOKEN))
class Checks(unittest.TestCase):
    def test_only_known_head_build_ids_and_no_private_messages_survive(self):
        result = m.classify([event()])
        self.assertTrue(result['matching_dispatch_found'])
        self.assertEqual(result['started_build_ids'], ['a'*24])
        self.assertNotIn(TOKEN, json.dumps(result))
    def test_wrong_head_and_branch_cannot_supply_a_build_id(self):
        for name in ('branch', 'commitHash'):
            value = event()
            value['request'][name] = 'other'
            self.assertFalse(m.classify([value])['matching_dispatch_found'])
    def test_unknown_app_and_untrusted_identifiers_are_omitted(self):
        value = event()
        value['results']['startedBuilds'] += [dict(id='b'*24, appId='other'), dict(id=TOKEN, appId=m.APP_ID)]
        self.assertEqual(m.classify([value])['started_build_ids'], ['a'*24])
    def test_request_is_bounded_same_origin_get_only(self):
        transport = Transport([event()])
        result = m.inspect(TOKEN, transport)
        self.assertEqual(result['status'], 'KNOWN_WEBHOOK_DISPATCH_READ')
        self.assertEqual(transport.requests[0].full_url, m.URL)
        self.assertEqual(transport.requests[0].method, 'GET')
        self.assertEqual(result['builds_started'], 0)
    def test_large_or_sensitive_failure_is_redacted_without_replay(self):
        for payload in (b'x'*(1024*1024+1), urllib.error.HTTPError(m.URL, 403, TOKEN, {}, io.BytesIO(TOKEN.encode()))):
            transport = Transport(payload)
            result = m.inspect(TOKEN, transport)
            self.assertEqual(result['status'], 'NOT_VERIFIED')
            self.assertNotIn(TOKEN, json.dumps(result))
            self.assertEqual(len(transport.requests), 1)
    def test_provider_reason_is_only_fixed_categories(self):
        value = event()
        value['results']['message'] = 'Invalid publishing app_store_connect integration ' + TOKEN
        result = m.classify([value])
        self.assertIn('CONFIGURATION_REJECTED', result['reason_codes'])
        self.assertIn('INTEGRATION_REFERENCE_REJECTED', result['reason_codes'])
        self.assertNotIn(TOKEN, json.dumps(result))
    def test_observed_webhook_response_envelope_is_recognized(self):
        value = event()
        value['response'] = value.pop('results')
        result = m.classify([value])
        self.assertTrue(result['matching_dispatch_found'])
        self.assertEqual(result['started_build_ids'], ['a'*24])
    def test_provider_task_result_and_error_are_classified_without_private_text(self):
        value = event()
        value['task'] = dict(finishedAt='2026-10-11', successful=True, result=value.pop('results'))
        self.assertEqual(m.classify([value])['started_build_ids'], ['a'*24])
        value['task'] = dict(finishedAt='2026-10-11', successful=False, errorMessage='Invalid publishing configuration ' + TOKEN)
        result = m.classify([value])
        self.assertTrue(result['task_finished'])
        self.assertFalse(result['task_successful'])
        self.assertIn('CONFIGURATION_REJECTED', result['reason_codes'])
        self.assertNotIn(TOKEN, json.dumps(result))
if __name__ == '__main__':
    unittest.main()
