from datetime import datetime, timedelta, timezone
import io
import json
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
from tools import apple_signing_resources as resources
from tools import signed_archive as archive
from tools.apple_signing_preflight import CheckError, IDENTIFIERS


class Transport:
    def __init__(self, data):
        self.data, self.requests = data, []
    def open(self, request, timeout):
        self.requests.append(request)
        return io.BytesIO(json.dumps(self.data).encode())


def profile():
    team = 'DEMO123456'
    return {'TeamIdentifier': [team], 'ExpirationDate': datetime.now(timezone.utc) + timedelta(days=20),
            'Entitlements': {'com.apple.developer.team-identifier': team,
                'application-identifier': team + '.' + IDENTIFIERS[0],
                'com.apple.security.application-groups': [archive.GROUP], 'get-task-allow': False}}


class Tests(unittest.TestCase):
    def test_manual_signing_uses_exact_three_distinct_profiles_and_matching_identity(self):
        materials = {identifier: {'uuid': str(i) * 8 + '-' + str(i) * 4 + '-' + str(i) * 4 + '-' + str(i) * 4 + '-' + str(i) * 12}
            for i, identifier in enumerate(IDENTIFIERS, 1)}
        settings = archive.manual_settings('DEMO123456', materials, 'a' * 40)
        self.assertEqual(set(settings), set(IDENTIFIERS))
        for identifier, value in settings.items():
            self.assertEqual(value['CODE_SIGN_STYLE'], 'Manual')
            self.assertEqual(value['PROVISIONING_PROFILE_SPECIFIER'], materials[identifier]['uuid'])
            self.assertEqual(value['CODE_SIGN_IDENTITY'], 'a' * 40)

    def test_manual_export_stays_internal_and_export_only(self):
        materials = {identifier: {'uuid': str(i) * 8 + '-' + str(i) * 4 + '-' + str(i) * 4 + '-' + str(i) * 4 + '-' + str(i) * 12}
            for i, identifier in enumerate(IDENTIFIERS, 1)}
        options = archive.export_options('DEMO123456', materials, 'b' * 40)
        self.assertEqual(options['signingStyle'], 'manual')
        self.assertEqual(options['provisioningProfiles'], {key: value['uuid'] for key, value in materials.items()})
        self.assertEqual(options['destination'], 'export')
        self.assertTrue(options['testFlightInternalTestingOnly'])
        self.assertFalse(options['uploadSymbols'])

    def test_manual_signing_refuses_missing_duplicate_or_arbitrary_profile_paths(self):
        duplicate = {identifier: {'uuid': '11111111-1111-1111-1111-111111111111'} for identifier in IDENTIFIERS}
        invalid = {identifier: {'uuid': '../private'} for identifier in IDENTIFIERS}
        for materials in ({}, duplicate, invalid):
            with self.assertRaisesRegex(CheckError, '^MANUAL_SIGNING_MATERIAL_UNVERIFIED$'):
                archive.manual_settings('DEMO123456', materials, 'a' * 40)

    def test_ci_profile_installation_is_private_and_never_overwrites(self):
        materials = {identifier: {'uuid': str(i) * 8 + '-' + str(i) * 4 + '-' + str(i) * 4 + '-' + str(i) * 4 + '-' + str(i) * 12,
            'content': b'synthetic-cms'} for i, identifier in enumerate(IDENTIFIERS, 1)}
        with tempfile.TemporaryDirectory() as directory, patch.object(archive.Path, 'home', return_value=Path(directory)):
            archive.install_profiles(materials)
            archive.install_profiles(materials)
            folder = Path(directory) / 'Library/Developer/Xcode/UserData/Provisioning Profiles'
            self.assertEqual(len(list(folder.glob('*.mobileprovision'))), 3)
            material = materials[IDENTIFIERS[0]]
            path = folder / (material['uuid'] + '.mobileprovision')
            path.write_bytes(b'existing-other-content')
            with self.assertRaisesRegex(CheckError, '^PROFILE_INSTALL_COLLISION$'):
                archive.install_profiles(materials)
            self.assertEqual(path.read_bytes(), b'existing-other-content')

    def test_ephemeral_identity_requires_its_password_and_preserves_matching_key(self):
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.serialization import pkcs12
        from cryptography.x509.oid import NameOID
        from tools.codemagic_signing_key import make_key
        key = resources.load_key(make_key())
        subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'Synthetic test identity')])
        now = datetime.now(timezone.utc)
        certificate = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now).not_valid_after(now + timedelta(days=1)).sign(key, hashes.SHA256()))
        payload = archive.identity_container(key, certificate, 'synthetic-passphrase-not-a-credential')
        loaded, cert, _ = pkcs12.load_key_and_certificates(payload, b'synthetic-passphrase-not-a-credential')
        self.assertEqual(loaded.private_numbers(), key.private_numbers())
        self.assertEqual(cert.public_bytes(serialization.Encoding.DER), certificate.public_bytes(serialization.Encoding.DER))
        for password in (None, b'wrong-synthetic-password'):
            with self.assertRaises(ValueError):
                pkcs12.load_key_and_certificates(payload, password)

    def test_only_three_known_bundle_payloads_are_allowed(self):
        for identifier in IDENTIFIERS:
            t = Transport({})
            resources.Client('synthetic', 'public-synthetic-csr', t).request('/v1/bundleIds', 'POST', body=resources.bundle_body(identifier))
            self.assertEqual(t.requests[0].method, 'POST')
        with self.assertRaises(CheckError):
            resources.bundle_body('jp.someone.else')

    def test_no_other_routes_deletion_or_certificate_payload_is_sent(self):
        t = Transport({})
        client = resources.Client('synthetic', 'public-synthetic-csr', t)
        for route, method, body in (('/v1/apps', 'POST', {}), ('/v1/certificates', 'DELETE', {}),
                                    ('/v1/certificates', 'POST', {'data': {'attributes': {'csrContent': 'other'}}}),
                                    ('/v1/bundleIds', 'POST', resources.bundle_body(IDENTIFIERS[0]) | {'extra': True})):
            with self.assertRaisesRegex(CheckError, '^UNAPPROVED_RESOURCE_REQUEST$'):
                client.request(route, method, body=body)
        self.assertEqual(t.requests, [])

    def test_certificate_post_contains_only_own_public_csr_and_distribution_type(self):
        t = Transport({})
        client = resources.Client('synthetic', 'public-synthetic-csr', t)
        body = {'data': {'type': 'certificates', 'attributes': {'certificateType': 'DISTRIBUTION', 'csrContent': client.csr}}}
        client.request('/v1/certificates', 'POST', body=body)
        self.assertEqual(json.loads(t.requests[0].data), body)
        self.assertNotIn('PRIVATE KEY', t.requests[0].data.decode())

    def test_resource_post_is_reserved_before_network_and_never_retried(self):
        events = []
        class Broken:
            def open(self, request, **kwargs):
                events.append('network')
                raise OSError('synthetic-secret-do-not-print')
        client = resources.Client('synthetic', 'public-synthetic-csr', Broken(), events.append)
        with self.assertRaisesRegex(CheckError, '^RESOURCE_REQUEST_OUTCOME_UNAVAILABLE$'):
            client.request('/v1/bundleIds', 'POST', body=resources.bundle_body(IDENTIFIERS[0]))
        self.assertEqual(events, ['BUNDLE_ID_POST_RESERVED', 'network'])

    def test_certificate_key_requires_rsa_2048(self):
        from tools.codemagic_signing_key import make_key
        self.assertEqual(resources.load_key(make_key()).key_size, 2048)
        for value in ('synthetic-secret-do-not-print', 'x' * 9000, None):
            with self.assertRaisesRegex(CheckError, '^CERTIFICATE_KEY_INVALID$'):
                resources.load_key(value)

    def test_export_is_internal_only_and_never_uploads(self):
        options = archive.export_options('DEMO123456')
        self.assertEqual(options['destination'], 'export')
        self.assertEqual(options['method'], 'app-store-connect')
        self.assertTrue(options['testFlightInternalTestingOnly'])
        self.assertFalse(options['uploadSymbols'])
        with self.assertRaises(CheckError):
            archive.export_options('unverified')

    def test_valid_exact_profile_is_accepted(self):
        archive.validate_profile(profile(), IDENTIFIERS[0], 'DEMO123456', True)

    def test_other_team_other_app_or_other_group_is_refused(self):
        for key, value in (('com.apple.developer.team-identifier', 'OTHER12345'),
                           ('application-identifier', 'DEMO123456.jp.other.app'),
                           ('com.apple.security.application-groups', ['group.other'])):
            p = profile()
            p['Entitlements'][key] = value
            with self.assertRaisesRegex(CheckError, '^PROFILE_ID_TEAM_OR_GROUP_MISMATCH$'):
                archive.validate_profile(p, IDENTIFIERS[0], 'DEMO123456')

    def test_distribution_profile_refuses_development_or_device_binding(self):
        for mode in ('development', 'devices', 'enterprise'):
            p = profile()
            if mode == 'development':
                p['Entitlements']['get-task-allow'] = True
            elif mode == 'devices':
                p['ProvisionedDevices'] = ['synthetic-device']
            else:
                p['ProvisionsAllDevices'] = True
            with self.assertRaisesRegex(CheckError, '^PROFILE_NOT_APP_STORE_DISTRIBUTION$'):
                archive.validate_profile(p, IDENTIFIERS[0], 'DEMO123456', True)

    def test_expired_profile_is_not_a_success(self):
        p = profile()
        p['ExpirationDate'] = datetime.now(timezone.utc) - timedelta(days=1)
        with self.assertRaisesRegex(CheckError, '^PROFILE_EXPIRED_OR_UNVERIFIED$'):
            archive.validate_profile(p, IDENTIFIERS[0], 'DEMO123456')

    def test_failure_classifier_does_not_return_account_or_log_text(self):
        private = b'synthetic-secret-do-not-print'
        self.assertEqual(archive.classify_build_failure(private + b' no devices registered'), 'DEVELOPMENT_PROFILE_DEVICE_REQUIRED')
        self.assertEqual(archive.classify_build_failure(private + b' com.apple.security.application-groups'), 'PROFILE_APP_GROUP_SETUP_REQUIRED')
        self.assertNotIn(private.decode(), archive.classify_build_failure(private))
        self.assertEqual(archive.classify_command_failure('keychain_import', private + b' MAC verification failed'), 'PKCS12_COMPATIBILITY_REQUIRED')
        self.assertNotIn(private.decode(), archive.classify_command_failure('keychain_import', private))


if __name__ == '__main__':
    unittest.main()
