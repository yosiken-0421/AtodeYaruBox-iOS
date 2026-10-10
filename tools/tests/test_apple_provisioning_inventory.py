from datetime import datetime, timedelta, timezone
import io
import json
import unittest
from tools import apple_provisioning_inventory as m
from tools import codemagic_signed_evidence as evidence
from tools.apple_signing_preflight import CheckError, IDENTIFIERS


class Transport:
    def __init__(self):
        self.requests = []
    def open(self, request, timeout):
        self.requests.append(request)
        return io.BytesIO(b'{"data": []}')


def mapping():
    return dict(zip(IDENTIFIERS, ('DEMOID0001', 'DEMOID0002', 'DEMOID0003')))


def profile(identifier):
    return {'ExpirationDate': datetime.now(timezone.utc) + timedelta(days=1),
        'Entitlements': {'application-identifier': 'DEMO123456.' + identifier,
            'com.apple.security.application-groups': [m.GROUP], 'get-task-allow': False},
        'private-name': 'synthetic-secret-do-not-print'}


class Checks(unittest.TestCase):
    def test_only_known_related_get_routes_are_requested(self):
        transport = Transport()
        reader = m.RelatedReader('synthetic-token', mapping(), transport)
        for identifier in IDENTIFIERS:
            reader.get(identifier, 'bundleIdCapabilities')
            reader.get(identifier, 'profiles')
        self.assertEqual(len(transport.requests), 6)
        self.assertTrue(all(r.method == 'GET' for r in transport.requests))
        for identifier, relation in (('another.app', 'profiles'), (IDENTIFIERS[0], 'certificates')):
            with self.assertRaisesRegex(CheckError, '^INVENTORY_ROUTE_REFUSED$'):
                reader.get(identifier, relation)
        self.assertEqual(len(transport.requests), 6)

    def test_unverified_identifiers_and_path_injection_are_refused(self):
        for change in ({IDENTIFIERS[0]: '../other'}, {IDENTIFIERS[0]: {}}, {IDENTIFIERS[0]: 'DEMOID0002'}):
            with self.assertRaisesRegex(CheckError, '^INVENTORY_IDENTIFIER_MAP_INVALID$'):
                m.RelatedReader('synthetic-token', mapping() | change, Transport())

    def test_summary_reports_only_counts_and_group_state(self):
        def getter(identifier, kind):
            return ([{'attributes': {'capabilityType': 'APP_GROUPS', 'secret': 'synthetic-secret-do-not-print'}}]
                if kind == 'bundleIdCapabilities' else
                [{'attributes': {'profileState': 'ACTIVE', 'profileType': 'IOS_APP_STORE', 'profileContent': identifier}}])
        result = m.summarize(getter, profile)
        self.assertTrue(all(v['app_groups_capability_enabled'] for v in result.values()))
        self.assertTrue(all(v['app_store_profiles_with_exact_group'] == 1 for v in result.values()))
        self.assertNotIn('synthetic-secret-do-not-print', json.dumps(result))

    def test_other_app_expired_profile_or_other_group_does_not_match(self):
        def getter(identifier, kind):
            return [] if kind == 'bundleIdCapabilities' else [{'attributes': {'profileState': 'ACTIVE', 'profileContent': identifier}}]
        for mode in ('other_app', 'expired', 'group'):
            def decoder(identifier):
                p = profile(identifier)
                if mode == 'other_app':
                    p['Entitlements']['application-identifier'] = 'DEMO123456.another.app'
                elif mode == 'expired':
                    p['ExpirationDate'] -= timedelta(days=3)
                else:
                    p['Entitlements']['com.apple.security.application-groups'] = ['group.other']
                return p
            self.assertTrue(all(v['active_profiles_with_exact_group'] == 0 for v in m.summarize(getter, decoder).values()))

    def test_development_and_device_bound_profiles_are_not_app_store_ready(self):
        def getter(identifier, kind):
            return [] if kind == 'bundleIdCapabilities' else [{'attributes': {'profileState': 'ACTIVE', 'profileType': 'IOS_APP_STORE', 'profileContent': identifier}}]
        def decoder(identifier):
            p = profile(identifier)
            p['ProvisionedDevices'] = ['synthetic-device']
            return p
        result = m.summarize(getter, decoder)
        self.assertTrue(all(v['active_profiles_with_exact_group'] == 1 and v['app_store_profiles_with_exact_group'] == 0 for v in result.values()))

    def test_public_evidence_cannot_expose_profile_values_or_claim_writes(self):
        inventory = {i: dict(app_groups_capability_enabled=False, profiles_returned=0,
            active_profiles_with_exact_group=0, app_store_profiles_with_exact_group=0) for i in IDENTIFIERS}
        payload = dict(status='SIGNING_INVENTORY_READ', stage='inventory', verified_native_source=evidence.NATIVE,
            signed_archive_verified=False, signed_ipa_verified=False, apple_resources_modified=False,
            binary_uploaded=False, billing_modified=False, private_key_disclosed=False, native_tests_repeated=False,
            provisioning_inventory=inventory, private='synthetic-secret-do-not-print')
        self.assertNotIn('synthetic-secret-do-not-print', json.dumps(evidence.sanitize(payload)))
        self.assertIsNone(evidence.sanitize(payload | {'apple_resources_modified': True}))
        inventory[IDENTIFIERS[0]]['profileContent'] = 'synthetic-secret-do-not-print'
        self.assertIsNone(evidence.sanitize(payload))


if __name__ == '__main__':
    unittest.main()
