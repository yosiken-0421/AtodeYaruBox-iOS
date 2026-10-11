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
    def test_owner_registration_never_reports_email_or_another_tester(self):
        p=dict(status='OWNER_INTERNAL_TESTFLIGHT_TESTER_REGISTERED',app_record_id='6821479152',
            apple_build_id='3dc8936a-6059-4ad2-b8c1-9ffcc555a7ea',group_id='b170086a-49ff-4990-b9cc-b68df67cd5df',
            tester_id='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',tester_state='INVITED',owner_email_matches=True,
            owner_tester_registered=True,owner_internal_group_verified=True,owner_internal_build_assigned=True,
            owner_testers_registered=1,other_testers_invited=0,public_link_enabled=False,automatic_future_builds=False,
            apple_resources_modified=True,binary_uploaded=False,billing_modified=False,private_key_disclosed=False,
            email='synthetic@example.invalid')
        self.assertTrue(m.sanitize(p)['owner_tester_registered'])
        self.assertNotIn('synthetic@example.invalid',json.dumps(m.sanitize(p)))
        for update in ({'other_testers_invited':1},{'owner_email_matches':False},{'public_link_enabled':True},{'group_id':'other'}):
            self.assertIsNone(m.sanitize(p | update))
    def test_read_only_group_shape_allows_nulls_without_private_messages(self):
        payload=dict(status='OWNER_TESTFLIGHT_GROUP_STATE_READ',app_record_id='6821479152',
            apple_build_id='3dc8936a-6059-4ad2-b8c1-9ffcc555a7ea',group_count=1,
            apple_resources_modified=False,binary_uploaded=False,billing_modified=False,private_key_disclosed=False,
            testers_invited=0,isInternalGroup=True,publicLinkEnabled=None,hasAccessToAllBuilds=False,private=TOKEN)
        self.assertIsNone(m.sanitize(payload)['publicLinkEnabled'])
        self.assertNotIn(TOKEN,json.dumps(m.sanitize(payload)))
        self.assertIsNone(m.sanitize(payload | {'testers_invited':1}))
    def test_owner_group_proof_cannot_disclose_or_invite_anybody(self):
        payload = dict(status='OWNER_INTERNAL_TESTFLIGHT_GROUP_READY', app_record_id='6821479152',
            apple_build_id='3dc8936a-6059-4ad2-b8c1-9ffcc555a7ea', group_id='b'*36,
            owner_internal_group_verified=True, owner_internal_build_assigned=True,
            public_link_enabled=False, automatic_future_builds=False, testers_invited=0,
            apple_resources_modified=True, binary_uploaded=False, billing_modified=False, private_key_disclosed=False, private=TOKEN)
        self.assertNotIn(TOKEN, json.dumps(m.sanitize(payload)))
        for change in ({'app_record_id':'other'}, {'public_link_enabled':True}, {'testers_invited':1}, {'automatic_future_builds':True}, {'group_id':TOKEN}):
            self.assertIsNone(m.sanitize(payload | change))
    def test_apple_read_requires_exact_eligible_internal_build_without_mutation(self):
        payload = report() | dict(status='APPLE_TESTFLIGHT_BUILD_READ', stage='testflight_read',
            apple_resources_modified=False, app_record_id='6821479152', app_store_binary_present=True,
            eligible_internal_testing=True, apple_build_id='a'*36, processing_state='VALID',
            internal_testing_only=True, metadata_verified=True, version='0.1.0', platform='IOS',
            uses_non_exempt_encryption=False, internal_beta_state='READY_FOR_BETA_TESTING', private=TOKEN)
        payload.pop('diagnostic')
        self.assertTrue(m.sanitize(payload)['eligible_internal_testing'])
        self.assertNotIn(TOKEN, json.dumps(m.sanitize(payload)))
        for change in ({'app_record_id':'other'}, {'processing_state':'PROCESSING'}, {'internal_testing_only':False},
                       {'metadata_verified':False}, {'uses_non_exempt_encryption':True}, {'platform':'MAC_OS'}, {'apple_build_id':TOKEN}):
            self.assertIsNone(m.sanitize(payload | change))
    def test_apple_pending_does_not_claim_a_present_or_installable_build(self):
        payload = report() | dict(status='APPLE_TESTFLIGHT_BUILD_PENDING', stage='testflight_read',
            apple_resources_modified=False, app_record_id='6821479152', app_store_binary_present=False,
            eligible_internal_testing=False)
        payload.pop('diagnostic')
        self.assertFalse(m.sanitize(payload)['eligible_internal_testing'])
        self.assertIsNone(m.sanitize(payload | {'eligible_internal_testing':True}))
        self.assertIsNone(m.sanitize(payload | {'app_store_binary_present':True}))
        self.assertIsNone(m.sanitize(payload | {'signed_archive_verified':True}))
    def test_app_record_evidence_only_accepts_verified_identity_without_writes(self):
        payload = report() | dict(status='APP_RECORD_READ', stage='app_record', apple_resources_modified=False,
            app_record_read_verified=True, app_record_exists=True, app_record_id='1234567890', private=TOKEN)
        payload.pop('diagnostic')
        self.assertNotIn(TOKEN, json.dumps(m.sanitize(payload)))
        for change in ({'app_record_id': TOKEN}, {'app_record_exists': False}, {'app_record_read_verified': False}, {'apple_resources_modified': True}):
            self.assertIsNone(m.sanitize(payload | change))

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
        result = m.classify_log((TOKEN + '\nRan 47 tests in 0.2s\n\nOK\n' + json.dumps({**report(), 'private': TOKEN})).encode())
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
