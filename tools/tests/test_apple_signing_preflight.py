"""Synthetic host checks, not Apple authentication or iOS XCTest results."""
import io
import base64
import json
from pathlib import Path
import tempfile
import urllib.error
import urllib.parse
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from tools import apple_signing_preflight as module


class SigningPreflightTests(unittest.TestCase):
    def environment(self):
        return {'APP_STORE_CONNECT_KEY_IDENTIFIER': 'DEMO123456',
                'APP_STORE_CONNECT_ISSUER_ID': '00000000-0000-0000-0000-000000000001',
                'APP_STORE_CONNECT_PRIVATE_KEY': '-----BEGIN PRIVATE KEY-----\nSYNTHETIC_SECRET_NEVER_PRINT\n-----END PRIVATE KEY-----'}

    def test_normalization_preserves_pem_and_accepts_only_encoded_pem(self):
        pem = self.environment()['APP_STORE_CONNECT_PRIVATE_KEY']
        self.assertEqual(module.normalize_private_key('\ufeff' + pem.replace('\n', '\r\n') + '\n'), (pem, 'PEM'))
        self.assertEqual(module.normalize_private_key(pem.replace('\n', '\\n')), (pem, 'ESCAPED_PEM'))
        self.assertEqual(module.normalize_private_key(base64.b64encode(pem.encode()).decode()), (pem, 'BASE64_PEM'))

    def test_malformed_key_is_refused_without_echoing_content(self):
        for value in ('SYNTHETIC_SECRET_NEVER_PRINT', '<html>SYNTHETIC_SECRET_NEVER_PRINT</html>',
                      base64.b64encode(b'SYNTHETIC_SECRET_NEVER_PRINT').decode(), 'x'*17000):
            with self.assertRaisesRegex(module.CheckError, '^PRIVATE_KEY_FORMAT_INVALID$'):
                module.normalize_private_key(value)

    def test_outside_or_non_key_file_reference_is_refused(self):
        for value in ('@file:/etc/passwd', '@file:/private/other.p8'):
            with self.assertRaisesRegex(module.CheckError, '^PRIVATE_KEY_REFERENCE_REFUSED$'):
                module.normalize_private_key(value)

    def test_ci_temporary_reference_accepts_extensionless_key_and_refuses_other_contents(self):
        with tempfile.TemporaryDirectory() as directory:
            key_file = Path(directory) / 'integration-key'
            pem = self.environment()['APP_STORE_CONNECT_PRIVATE_KEY']
            key_file.write_text(pem, encoding='utf-8')
            self.assertEqual(module.normalize_private_key('@file:' + str(key_file)), (pem, 'FILE_REFERENCE'))
            key_file.write_text('SYNTHETIC_SECRET_NEVER_PRINT', encoding='utf-8')
            with self.assertRaisesRegex(module.CheckError, '^PRIVATE_KEY_FORMAT_INVALID$'):
                module.normalize_private_key('@file:' + str(key_file))

    def test_real_ephemeral_p256_signature_with_pinned_runtime(self):
        import jwt
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives import serialization
        key = ec.generate_private_key(ec.SECP256R1())
        pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                serialization.NoEncryption()).decode()
        for value in (pem, pem.strip().replace('\n', '\\n'), base64.b64encode(pem.encode()).decode()):
            env = {**self.environment(), 'APP_STORE_CONNECT_PRIVATE_KEY': value}
            token = module.token_from_environment(env)
            payload = jwt.decode(token, key.public_key(), algorithms=['ES256'], audience='appstoreconnect-v1')
            self.assertEqual(payload['exp'] - payload['iat'], 300)
            self.assertEqual(payload['scope'], module.approved_scope())

    def test_token_only_authorizes_gets_for_five_minutes(self):
        captured = {}
        def encoder(payload, key, **options):
            captured.update(payload=payload, key=key, options=options)
            return 'synthetic-token'
        module.token_from_environment(self.environment(), encoder, now=1000)
        actual = []
        def getter(route, query):
            actual.append('GET ' + route + '?' + urllib.parse.urlencode(query))
            return {'data': []}
        module.collect(getter)
        self.assertEqual(captured['payload']['scope'], actual)
        self.assertEqual(len(actual), 4)
        self.assertTrue(all(method.startswith('GET /v1/') for method in actual))
        self.assertEqual([urllib.parse.parse_qs(urllib.parse.urlsplit(s[4:]).query)['filter[identifier]'][0]
                          for s in actual[:3]], list(module.IDENTIFIERS))
        self.assertEqual(captured['payload']['exp'] - captured['payload']['iat'], 300)
        self.assertEqual(captured['options']['algorithm'], 'ES256')

    def test_missing_credentials_are_not_an_authentication_pass(self):
        with self.assertRaisesRegex(module.CheckError, '^INTEGRATION_CREDENTIALS_MISSING$'):
            module.token_from_environment({})

    def test_main_filter_can_return_extensions_but_only_exact_unique_id_is_selected(self):
        entries = [{'attributes': {'identifier': i}} for i in module.IDENTIFIERS]
        for identifier in module.IDENTIFIERS:
            selected = module.exact_bundle_rows(entries, identifier)
            self.assertEqual([e['attributes']['identifier'] for e in selected], [identifier])
        with self.assertRaisesRegex(module.CheckError, '^BUNDLE_IDENTIFIER_AMBIGUOUS$'):
            module.exact_bundle_rows(entries + [entries[0]], module.IDENTIFIERS[0])
        with self.assertRaisesRegex(module.CheckError, '^BUNDLE_IDENTIFIER_AMBIGUOUS$'):
            module.exact_bundle_rows([{'attributes': {'identifier': 'another.app'}}], module.IDENTIFIERS[0])

    def test_invalid_identifiers_are_rejected(self):
        for name, invalid in [('APP_STORE_CONNECT_KEY_IDENTIFIER', 'not-valid'),
                              ('APP_STORE_CONNECT_ISSUER_ID', 'SENSITIVE-INPUT')]:
            environment = self.environment()
            environment[name] = invalid
            with self.subTest(name=name), self.assertRaisesRegex(
                    module.CheckError, '^INTEGRATION_CREDENTIALS_INVALID$'):
                module.token_from_environment(environment, lambda *a, **k: 'unused')

    def test_signing_exception_does_not_leak_secret(self):
        def encoder(*args, **kwargs):
            raise ValueError('SYNTHETIC_SECRET_NEVER_PRINT')
        with self.assertRaisesRegex(module.CheckError, '^JWT_SIGNING_FAILED$'):
            module.token_from_environment(self.environment(), encoder)

    def test_unapproved_routes_never_reach_network(self):
        reader = module.AppleReader('synthetic-token')
        for route in ['/v1/apps', '/v1/certificates/delete', 'https://example.com']:
            with self.subTest(route=route), self.assertRaisesRegex(module.CheckError, '^UNAPPROVED_ROUTE$'):
                reader.get(route, {})

    def test_other_apps_are_not_queried(self):
        with self.assertRaisesRegex(module.CheckError, '^UNAPPROVED_IDENTIFIER$'):
            module.AppleReader('unused').get('/v1/bundleIds', {'filter[identifier]': 'another.app'})

    def test_redirect_cannot_forward_bearer_token(self):
        with self.assertRaisesRegex(module.CheckError, '^REDIRECT_REFUSED$'):
            module.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://example.com')

    def test_pagination_is_not_silently_accepted(self):
        with self.assertRaisesRegex(module.CheckError, '^PAGINATED_RESPONSE_REQUIRES_REVIEW$'):
            module.rows({'data': [], 'links': {'next': 'https://example.com'}})

    def test_authentication_does_not_claim_signed_build_readiness(self):
        requests = []
        def getter(route, query):
            requests.append((route, query))
            return {'data': []}
        result = module.collect(getter)
        self.assertEqual(len(requests), 4)
        self.assertEqual(set(result['bundle_identifiers'].values()), {'NOT_REGISTERED'})
        self.assertEqual(result['status'], 'APPLE_READ_AUTHENTICATED')
        self.assertFalse(result['signed_build_ready'])
        self.assertFalse(result['apple_resources_modified'])

    def test_wrong_bundle_is_not_accepted(self):
        with self.assertRaisesRegex(module.CheckError, '^BUNDLE_IDENTIFIER_AMBIGUOUS$'):
            module.collect(lambda *a: {'data': [{'attributes': {'identifier': 'another.app'}}]})

    def test_old_pass_is_replaced_and_exception_is_not_printed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'artifacts').mkdir()
            target = root / 'artifacts/apple-signing-preflight.json'
            target.write_text('{"authentication_verified":true}')
            output = io.StringIO()
            with patch.object(module, 'ROOT', root), patch.object(module, 'token_from_environment',
                    side_effect=ValueError('SYNTHETIC_SECRET_NEVER_PRINT')), redirect_stdout(output):
                self.assertEqual(module.main(), 1)
            self.assertFalse(json.loads(target.read_text())['authentication_verified'])
            self.assertNotIn('SYNTHETIC_SECRET_NEVER_PRINT', output.getvalue())
            self.assertNotIn('SYNTHETIC_SECRET_NEVER_PRINT', target.read_text())

    def test_interruption_does_not_leave_previous_authentication_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'artifacts').mkdir()
            target = root / 'artifacts/apple-signing-preflight.json'
            target.write_text('{"authentication_verified":true}')
            with patch.object(module, 'ROOT', root), patch.object(module, 'token_from_environment',
                    side_effect=KeyboardInterrupt()), self.assertRaises(KeyboardInterrupt):
                module.main()
            self.assertFalse(json.loads(target.read_text())['authentication_verified'])

    def test_http_error_body_and_url_are_not_exposed(self):
        class Opener:
            body = b'SYNTHETIC_SECRET_NEVER_PRINT'
            def open(self, request, **kwargs):
                raise urllib.error.HTTPError('SYNTHETIC_SECRET_NEVER_PRINT', 403,
                    'SYNTHETIC_SECRET_NEVER_PRINT', {}, io.BytesIO(self.body))
        for body, kind in ((b'SYNTHETIC_SECRET_NEVER_PRINT', 'UNKNOWN'),
                           (json.dumps({'errors': [{'code': 'FORBIDDEN_ERROR',
                            'detail': 'SYNTHETIC_SECRET_NEVER_PRINT'}]}).encode(), 'FORBIDDEN')):
            opener = Opener()
            opener.body = body
            with self.assertRaisesRegex(module.CheckError, '^APPLE_HTTP_403$') as context:
                module.AppleReader('synthetic-token', opener).get('/v1/bundleIds',
                    {'filter[identifier]': module.IDENTIFIERS[0]})
            self.assertEqual(context.exception.http_route, 'BUNDLE_IDS')
            self.assertEqual(context.exception.apple_error_kind, kind)
            self.assertNotIn('SYNTHETIC_SECRET_NEVER_PRINT', str(context.exception.__dict__))


if __name__ == '__main__':
    unittest.main()
