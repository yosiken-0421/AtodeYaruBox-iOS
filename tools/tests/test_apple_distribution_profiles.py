from datetime import datetime, timedelta, timezone
import io
import base64
import json
import unittest
import urllib.error

from tools import apple_distribution_profiles as m
from tools.apple_signing_preflight import IDENTIFIERS, CheckError
from tools.apple_provisioning_inventory import GROUP
from tools import codemagic_signed_evidence as evidence

TOKEN = 'synthetic-token-do-not-print'
TEAM = 'DEMO123456'
CERT = b'synthetic-public-certificate'


def profile():
    return {'TeamIdentifier': [TEAM], 'ExpirationDate': datetime.now(timezone.utc) + timedelta(days=1),
        'DeveloperCertificates': [CERT], 'Entitlements': {'com.apple.developer.team-identifier': TEAM,
            'application-identifier': TEAM + '.' + IDENTIFIERS[0],
            'com.apple.security.application-groups': [GROUP], 'get-task-allow': False}}


class Checks(unittest.TestCase):
    def test_owner_refresh_uses_one_fixed_revision_and_preserves_old_profile(self):
        name = m.REFRESHED_NAMES[IDENTIFIERS[0]]
        old = {'attributes': {'name': m.NAMES[IDENTIFIERS[0]], 'profileState': 'INVALID'}}
        entry = {'attributes': {'name': name, 'profileType': 'IOS_APP_STORE', 'profileState': 'ACTIVE',
            'profileContent': base64.b64encode(CERT).decode()}}
        class Creator:
            calls = 0
            def create(self, identifier):
                self.calls += 1
                return entry
        creator = Creator()
        decoded = profile() | {'Name': name, 'UUID': '11111111-1111-1111-1111-111111111111'}
        material = m.select_material([old], IDENTIFIERS[0], creator, CERT, TEAM, True, lambda _: decoded)
        self.assertEqual(creator.calls, 1)
        self.assertEqual(material['content'], CERT)
        self.assertEqual(old['attributes']['profileState'], 'INVALID')
        self.assertEqual(m.body(IDENTIFIERS[0], 'DEMOID0001', 'DEMOCERT01', True)['data']['attributes']['name'], name)

    def test_valid_revision_reused_and_invalid_revision_never_replaced_again(self):
        name = m.REFRESHED_NAMES[IDENTIFIERS[0]]
        entry = {'attributes': {'name': name, 'profileType': 'IOS_APP_STORE', 'profileState': 'ACTIVE',
            'profileContent': base64.b64encode(CERT).decode()}}
        class Creator:
            def create(self, identifier):
                raise AssertionError('Existing revision must not trigger POST')
        decoded = profile() | {'Name': name, 'UUID': '11111111-1111-1111-1111-111111111111'}
        m.select_material([entry], IDENTIFIERS[0], Creator(), CERT, TEAM, True, lambda _: decoded)
        entry['attributes']['profileState'] = 'INVALID'
        with self.assertRaisesRegex(CheckError, '^PROFILE_NOT_APP_STORE_DISTRIBUTION$'):
            m.select_material([entry], IDENTIFIERS[0], Creator(), CERT, TEAM, True, lambda _: decoded)

    def test_duplicate_revision_refused_before_mutation(self):
        entry = {'attributes': {'name': m.REFRESHED_NAMES[IDENTIFIERS[0]]}}
        class Creator:
            def create(self, identifier):
                raise AssertionError('Ambiguity must not trigger POST')
        with self.assertRaisesRegex(CheckError, '^PROFILE_OWNED_MATCH_AMBIGUOUS$'):
            m.select_material([entry, entry], IDENTIFIERS[0], Creator(), CERT, TEAM, True)

    def test_installed_profile_requires_matching_name_and_safe_uuid(self):
        name = m.REFRESHED_NAMES[IDENTIFIERS[0]]
        entry = {'attributes': {'name': name, 'profileType': 'IOS_APP_STORE', 'profileState': 'ACTIVE',
            'profileContent': base64.b64encode(CERT).decode()}}
        for value in ({'Name': 'unrelated', 'UUID': '11111111-1111-1111-1111-111111111111'},
                {'Name': name, 'UUID': '../arbitrary-file'}):
            with self.assertRaisesRegex(CheckError, '^PROFILE_NAME_OR_UUID_UNVERIFIED$'):
                m.select_material([entry], IDENTIFIERS[0], None, CERT, TEAM, True, lambda _: profile() | value)

    def test_only_exact_task_certificate_and_no_device_payload_can_be_created(self):
        class Transport:
            requests = []
            def open(self, request, timeout):
                self.requests.append(request)
                return io.BytesIO(b'{"data":{"type":"profiles","attributes":{}}}')
        transport, events = Transport(), []
        mapping = dict(zip(IDENTIFIERS, ('DEMOID0001', 'DEMOID0002', 'DEMOID0003')))
        creator = m.Creator(TOKEN, mapping, 'DEMOCERT01', events.append, transport)
        creator.create(IDENTIFIERS[0])
        request = transport.requests[0]
        self.assertEqual(request.full_url, 'https://api.appstoreconnect.apple.com/v1/profiles')
        self.assertEqual(request.method, 'POST')
        self.assertEqual(json.loads(request.data), m.body(IDENTIFIERS[0], 'DEMOID0001', 'DEMOCERT01'))
        self.assertNotIn('devices', json.loads(request.data)['data']['relationships'])
        self.assertEqual(events, ['PROFILE_POST_RESERVED', 'PROFILE_CREATED'])
        for identifier in (IDENTIFIERS[0], 'another.app'):
            with self.assertRaisesRegex(CheckError, '^PROFILE_ROUTE_OR_REPLAY_REFUSED$'):
                creator.create(identifier)
        self.assertEqual(len(transport.requests), 1)
        with self.assertRaisesRegex(CheckError, '^PROFILE_RESOURCE_ID_UNVERIFIED$'):
            m.body(IDENTIFIERS[0], '../other', 'DEMOCERT01')

    def test_uncertain_post_is_reserved_and_not_retried(self):
        class Failed:
            requests = 0
            def open(self, request, timeout):
                self.requests += 1
                raise urllib.error.URLError('synthetic-private-error')
        transport, events = Failed(), []
        creator = m.Creator(TOKEN, dict(zip(IDENTIFIERS, ('DEMOID0001', 'DEMOID0002', 'DEMOID0003'))), 'DEMOCERT01', events.append, transport)
        with self.assertRaisesRegex(CheckError, '^PROFILE_REQUEST_OUTCOME_UNAVAILABLE$'):
            creator.create(IDENTIFIERS[0])
        with self.assertRaisesRegex(CheckError, '^PROFILE_ROUTE_OR_REPLAY_REFUSED$'):
            creator.create(IDENTIFIERS[0])
        self.assertEqual(transport.requests, 1)
        self.assertEqual(events, ['PROFILE_POST_RESERVED'])

    def test_profile_requires_exact_group_team_certificate_and_device_free_distribution(self):
        entry = {'attributes': {'profileType': 'IOS_APP_STORE', 'profileState': 'ACTIVE', 'profileContent': TOKEN}}
        self.assertEqual(m.verify_profile(entry, IDENTIFIERS[0], CERT, TEAM, lambda _: profile())['TeamIdentifier'], [TEAM])
        for change, diagnostic in (({'DeveloperCertificates': [b'other']}, 'PROFILE_CERTIFICATE_MISMATCH'),
                ({'ProvisionedDevices': ['synthetic-device']}, 'PROFILE_NOT_APP_STORE_DISTRIBUTION'),
                ({'ExpirationDate': datetime.now(timezone.utc) - timedelta(days=1)}, 'PROFILE_EXPIRED_OR_UNVERIFIED'),
                ({'TeamIdentifier': ['OTHER12345']}, 'PROFILE_ID_TEAM_OR_GROUP_MISMATCH')):
            with self.assertRaisesRegex(CheckError, '^' + diagnostic + '$'):
                m.verify_profile(entry, IDENTIFIERS[0], CERT, TEAM, lambda _: profile() | change)
        missing = profile()
        missing['Entitlements'].pop('com.apple.security.application-groups')
        with self.assertRaisesRegex(CheckError, '^APP_GROUP_PROFILE_ASSIGNMENT_REQUIRED$'):
            m.verify_profile(entry, IDENTIFIERS[0], CERT, TEAM, lambda _: missing)

    def test_public_evidence_only_accepts_verified_three_profiles_and_safe_counts(self):
        payload = dict(status='DISTRIBUTION_PROFILES_VERIFIED', stage='profile_prepare', verified_native_source=evidence.NATIVE,
            signed_archive_verified=False, signed_ipa_verified=False, apple_resources_modified=True, binary_uploaded=False,
            billing_modified=False, private_key_disclosed=False, native_tests_repeated=False,
            distribution_profiles_verified=True, verified_distribution_profiles=3, profiles_created_count=3, private=TOKEN)
        self.assertNotIn(TOKEN, json.dumps(evidence.sanitize(payload)))
        for change in ({'verified_distribution_profiles': 2}, {'profiles_created_count': 4}, {'binary_uploaded': True},
                {'distribution_profiles_verified': False}, {'verified_distribution_profiles': True}):
            self.assertIsNone(evidence.sanitize(payload | change))


if __name__ == '__main__':
    unittest.main()
