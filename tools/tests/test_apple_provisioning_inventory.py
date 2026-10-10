from datetime import datetime, timedelta, timezone
import io
import json
import unittest
import urllib.error
import urllib.parse
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
    def test_bad_request_retries_once_without_sparse_fields(self):
        class SparseFailure(Transport):
            def open(self, request, timeout):
                self.requests.append(request)
                if len(self.requests) == 1:
                    raise urllib.error.HTTPError(request.full_url, 400, 'synthetic-private-message', {},
                        io.BytesIO(b'{"errors":[{"code":"PARAMETER_ERROR.INVALID","source":{"parameter":"fields[profiles]"}}]}'))
                return io.BytesIO(b'{"data": []}')
        transport = SparseFailure()
        self.assertEqual(m.RelatedReader('synthetic-token', mapping(), transport).get(IDENTIFIERS[0], 'profiles'), [])
        self.assertEqual(len(transport.requests), 2)
        self.assertEqual(urllib.parse.parse_qs(urllib.parse.urlsplit(transport.requests[1].full_url).query), {'limit': ['200']})
        self.assertTrue(all(r.method == 'GET' for r in transport.requests))

    def test_failure_details_are_bounded_and_never_include_private_messages(self):
        class Failed(Transport):
            def open(self, request, timeout):
                self.requests.append(request)
                raise urllib.error.HTTPError(request.full_url, 400, 'synthetic-private-message', {},
                    io.BytesIO(b'{"errors":[{"code":"synthetic-private-code","source":{"parameter":"synthetic-private-id"},"detail":"synthetic-secret-do-not-print"}]}'))
        transport = Failed()
        with self.assertRaises(m.InventoryError) as caught:
            m.RelatedReader('synthetic-token', mapping(), transport).get(IDENTIFIERS[0], 'bundleIdCapabilities')
        self.assertEqual(len(transport.requests), 2)
        self.assertEqual(caught.exception.details, dict(relationship='bundleIdCapabilities', apple_error_code='UNKNOWN', parameter='UNKNOWN'))
        self.assertNotIn('synthetic-private', json.dumps(caught.exception.details))
        self.assertEqual(m.InventoryError('RESOURCE_HTTP_400', 'profiles', {}, []).details['apple_error_code'], 'UNKNOWN')

    def test_permissions_failure_is_not_retried(self):
        class Denied(Transport):
            def open(self, request, timeout):
                self.requests.append(request)
                raise urllib.error.HTTPError(request.full_url, 403, 'private', {}, io.BytesIO(b'{}'))
        transport = Denied()
        with self.assertRaisesRegex(m.InventoryError, '^RESOURCE_HTTP_403$'):
            m.RelatedReader('synthetic-token', mapping(), transport).get(IDENTIFIERS[0], 'profiles')
        self.assertEqual(len(transport.requests), 1)

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
        details = dict(relationship='profiles', apple_error_code='PARAMETER_ERROR.INVALID', parameter='fields[profiles]')
        failed = payload | dict(status='NOT_VERIFIED', diagnostic='RESOURCE_HTTP_400', inventory_failure=details)
        self.assertEqual(evidence.sanitize(failed)['inventory_failure'], details)
        self.assertIsNone(evidence.sanitize(failed | {'inventory_failure': details | {'parameter': 'synthetic-private-id'}}))
        self.assertIsNone(evidence.sanitize(failed | {'inventory_failure': details | {'apple_error_code': {}}}))
        inventory[IDENTIFIERS[0]]['profileContent'] = 'synthetic-secret-do-not-print'
        self.assertIsNone(evidence.sanitize(payload))


if __name__ == '__main__':
    unittest.main()
