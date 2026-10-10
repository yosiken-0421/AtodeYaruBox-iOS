import io
import json
import unittest
import urllib.error
from unittest.mock import patch
from tools import apple_app_record as m
from tools.apple_signing_preflight import CheckError, IDENTIFIERS

TOKEN = 'synthetic-token-not-a-credential'


class Transport:
    def __init__(self, value):
        self.value, self.requests = value, []
    def open(self, request, timeout):
        self.requests.append(request)
        return io.BytesIO(self.value if isinstance(self.value, bytes) else json.dumps(self.value).encode())


class Checks(unittest.TestCase):
    def test_exact_app_get_returns_id_without_private_response_or_other_apps(self):
        transport = Transport({'data': [{'type': 'apps', 'id': '1234567890',
            'attributes': {'bundleId': IDENTIFIERS[0], 'name': TOKEN}}]})
        result = m.read(TOKEN, transport)
        self.assertEqual(result, dict(app_record_read_verified=True, app_record_exists=True, app_record_id='1234567890'))
        self.assertNotIn(TOKEN, json.dumps(result))
        self.assertEqual([(r.method, r.full_url) for r in transport.requests], [('GET', m.URL)])

    def test_empty_record_is_verified_absent_but_other_identity_or_duplicates_refused(self):
        self.assertEqual(m.read(TOKEN, Transport({'data': []})), dict(app_record_read_verified=True, app_record_exists=False))
        entry = {'type': 'apps', 'id': '1234567890', 'attributes': {'bundleId': IDENTIFIERS[0]}}
        for entries in ([entry, entry], [entry | {'id': TOKEN}],
                [entry | {'attributes': {'bundleId': 'jp.other.app'}}]):
            with self.assertRaisesRegex(CheckError, '^APP_RECORD_IDENTITY_UNVERIFIED$'):
                m.read(TOKEN, Transport({'data': entries}))

    def test_bounded_response_and_http_errors_never_disclose_raw_messages(self):
        with self.assertRaisesRegex(CheckError, '^APP_RECORD_RESPONSE_LIMIT$'):
            m.read(TOKEN, Transport(b'x' * (64 * 1024 + 1)))
        class Failed:
            def open(self, request, timeout):
                raise urllib.error.HTTPError(m.URL, 403, TOKEN, {}, None)
        with self.assertRaisesRegex(CheckError, '^APPLE_HTTP_403$'):
            m.read(TOKEN, Failed())

    def test_jwt_scope_exactly_matches_filtered_fields_get(self):
        claims = []
        def encode(payload, key, **kwargs):
            claims.append(payload)
            return TOKEN
        def source(environment, encoder):
            return encoder({'scope': ['GET /another-resource'], 'exp': 300}, TOKEN)
        with patch.object(m, 'token_from_environment', side_effect=source):
            self.assertEqual(m.token({}, encode), TOKEN)
        self.assertEqual(claims[0]['scope'], ['GET ' + m.ROUTE])
        self.assertEqual(claims[0]['exp'], 300)


if __name__ == '__main__':
    unittest.main()
