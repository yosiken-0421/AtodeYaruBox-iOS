"""Synthetic host checks, not Apple authentication or iOS XCTest results."""
import io
import json
from pathlib import Path
import tempfile
import urllib.error
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from tools import apple_signing_preflight as module


class SigningPreflightTests(unittest.TestCase):
    def environment(self):
        return {'APP_STORE_CONNECT_KEY_IDENTIFIER': 'DEMO123456',
                'APP_STORE_CONNECT_ISSUER_ID': '00000000-0000-0000-0000-000000000001',
                'APP_STORE_CONNECT_PRIVATE_KEY': 'SYNTHETIC_SECRET_NEVER_PRINT'}

    def test_token_only_authorizes_gets_for_five_minutes(self):
        captured = {}
        def encoder(payload, key, **options):
            captured.update(payload=payload, key=key, options=options)
            return 'synthetic-token'
        module.token_from_environment(self.environment(), encoder, now=1000)
        self.assertEqual(captured['payload']['scope'],
                         ['GET /v1/bundleIds', 'GET /v1/certificates'])
        self.assertEqual(captured['payload']['exp'] - captured['payload']['iat'], 300)
        self.assertEqual(captured['options']['algorithm'], 'ES256')

    def test_missing_credentials_are_not_an_authentication_pass(self):
        with self.assertRaisesRegex(module.CheckError, '^INTEGRATION_CREDENTIALS_MISSING$'):
            module.token_from_environment({})

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
            def open(self, request, **kwargs):
                raise urllib.error.HTTPError('SYNTHETIC_SECRET_NEVER_PRINT', 403,
                    'SYNTHETIC_SECRET_NEVER_PRINT', {}, io.BytesIO(b'SYNTHETIC_SECRET_NEVER_PRINT'))
        with self.assertRaisesRegex(module.CheckError, '^APPLE_HTTP_403$'):
            module.AppleReader('synthetic-token', Opener()).get('/v1/bundleIds',
                {'filter[identifier]': module.IDENTIFIERS[0]})


if __name__ == '__main__':
    unittest.main()
