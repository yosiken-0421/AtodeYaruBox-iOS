import io
import json
import unittest
from tools import codemagic_signed_evidence as m

TOKEN = 'synthetic-token-not-a-real-credential'
URL = 'https://storage.googleapis.com/synthetic/' + m.NAME


def report():
    return dict(status='NOT_VERIFIED', stage='archive', signed_archive_verified=False,
        signed_ipa_verified=False, apple_resources_modified=True, binary_uploaded=False,
        billing_modified=False, private_key_disclosed=False, native_tests_repeated=False,
        verified_native_source=m.NATIVE, diagnostic='PROFILE_APP_GROUP_SETUP_REQUIRED')


def build():
    return {'data': dict(id=m.BUILD, app_id=m.APP_ID, branch=m.BRANCH,
        commit={'hash': m.COMMIT}, status='failed',
        artifacts=[dict(name=m.NAME, short_lived_download_url=URL)])}


class Transport:
    def __init__(self, *values):
        self.values, self.requests = list(values), []
    def open(self, request, timeout):
        self.requests.append(request)
        value = self.values.pop(0)
        return io.BytesIO(value if isinstance(value, bytes) else json.dumps(value).encode())


class Checks(unittest.TestCase):
    def test_known_report_get_only_no_storage_credentials_or_private_contents(self):
        api, storage = Transport(build()), Transport({**report(), 'private': TOKEN})
        result = m.inspect(TOKEN, api, storage)
        self.assertEqual(result['status'], 'KNOWN_SIGNED_REPORT_READ')
        self.assertEqual([r.method for r in api.requests + storage.requests], ['GET', 'GET'])
        self.assertNotIn('X-auth-token', storage.requests[0].headers)
        self.assertNotIn(TOKEN, json.dumps(result))
        self.assertNotIn(URL, json.dumps(result))

    def test_identity_mismatch_prevents_artifact_or_log_download(self):
        for field, value in (('id', '0'*24), ('app_id', '0'*24), ('branch', 'main'), ('commit', {'hash': '0'*40})):
            data = build()
            data['data'][field] = value
            api, storage = Transport(data), Transport({})
            self.assertEqual(m.inspect(TOKEN, api, storage)['diagnostic'], 'BUILD_IDENTITY_UNVERIFIED')
            self.assertEqual(len(api.requests), 1)
            self.assertEqual(storage.requests, [])

    def test_signed_success_requires_complete_verified_three_target_package(self):
        good = {**report(), 'status': 'SIGNED_PACKAGE_VERIFIED', 'stage': 'complete',
            'signed_archive_verified': True, 'signed_ipa_verified': True,
            'all_three_bundle_ids_available': True, 'matching_certificate_key_verified': True,
            'team_identifier_verified': True, 'ipa_sha256': 'a'*64, 'ipa_size_bytes': 1024}
        good.pop('diagnostic')
        self.assertEqual(m.sanitize(good), good)
        for field in ('signed_archive_verified', 'all_three_bundle_ids_available', 'matching_certificate_key_verified', 'team_identifier_verified'):
            self.assertIsNone(m.sanitize({**good, field: False}))
        self.assertIsNone(m.sanitize({**good, 'ipa_sha256': TOKEN}))

    def test_upload_payment_disclosure_arbitrary_diagnostics_refused(self):
        for field in ('binary_uploaded', 'billing_modified', 'private_key_disclosed', 'native_tests_repeated'):
            self.assertIsNone(m.sanitize({**report(), field: True}))
        for change in ({'diagnostic': TOKEN}, {'compile_errors': True}, {'bundle_ids_created': [{}]},
                       {'bundle_ids_created': ['another.app']}, {'stage': []}, {'status': {}}):
            self.assertIsNone(m.sanitize({**report(), **change}))

    def test_only_fixed_log_flags_and_whitelisted_report_survive(self):
        result = m.classify_log((TOKEN + '\nRan 37 tests in 0.2s\n\nOK\n' + json.dumps({**report(), 'private': TOKEN})).encode())
        self.assertTrue(result['unit_checks_passed'])
        self.assertEqual(result['signed_report'], report())
        self.assertNotIn(TOKEN, json.dumps(result))
        self.assertFalse(m.classify_log(b'Ran 18 tests in 0.2s\n\nOK\n')['unit_checks_passed'])

    def test_wrong_urls_and_secret_files_refused(self):
        for url in ('https://evil.example/'+m.NAME, 'http://storage.googleapis.com/'+m.NAME,
                    'https://api.codemagic.io@evil.example/'+m.NAME, 'https://api.codemagic.io/private.p8'):
            self.assertFalse(m.download_url(url, m.NAME))

    def test_exact_known_step_log_token_remains_same_origin(self):
        data = build()
        data['data']['artifacts'] = []
        metadata = dict(application={'_id': m.APP_ID}, build={'_id': m.BUILD, 'buildActions': [
            {}, {}, dict(title=m.STEP, subactions=[{'logUrl': 'https://api.codemagic.io/synthetic-log'}])]})
        api = Transport(data, metadata, json.dumps(report()).encode())
        result = m.inspect(TOKEN, api, Transport())
        self.assertEqual(result['signed_report'], report())
        self.assertEqual(len(api.requests), 3)
        self.assertTrue(all(r.method == 'GET' for r in api.requests))
        self.assertEqual(api.requests[-1].headers['X-auth-token'], TOKEN)
        self.assertNotIn(TOKEN, json.dumps(result))


if __name__ == '__main__':
    unittest.main()
