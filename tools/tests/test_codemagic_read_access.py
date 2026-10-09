import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import urllib.error

from tools import codemagic_read_access as check

TOKEN = "fixture-token-only-not-a-credential-123456789"


class ReadAccessTests(unittest.TestCase):
    def response(self, value):
        stream = io.BytesIO(value if isinstance(value, bytes) else json.dumps(value).encode())
        opener = Mock()
        opener.open.return_value = stream
        return opener

    def test_missing_and_invalid_tokens_never_call_network(self):
        opener = Mock()
        for token in ("", "short", TOKEN + "\nInjected: header", "-----BEGIN PRIVATE KEY-----"):
            with self.subTest(token_type=len(token)):
                self.assertIn(check.read_application(token, opener)["status"],
                              {"CODEMAGIC_TOKEN_MISSING", "CODEMAGIC_TOKEN_INVALID"})
        opener.open.assert_not_called()

    def test_only_exact_app_is_requested_with_get(self):
        opener = self.response({"application": {"_id": check.APP_ID}})
        result = check.read_application(TOKEN, opener)
        request = opener.open.call_args.args[0]
        self.assertEqual(request.full_url, check.ENDPOINT)
        self.assertEqual(request.get_method(), "GET")
        self.assertIsNone(request.data)
        self.assertEqual(request.get_header("X-auth-token"), TOKEN)
        self.assertTrue(result["app_id_matched"])
        self.assertEqual(result["builds_started"], 0)
        self.assertFalse(result["integration_resolution_verified"])
        self.assertFalse(result["apple_authentication_verified"])

    def test_wrong_app_cannot_be_reported_as_authenticated(self):
        result = check.read_application(TOKEN, self.response({"application": {"_id": "another-app"}}))
        self.assertEqual(result["status"], "APP_RESPONSE_IDENTITY_UNVERIFIED")

    def test_success_does_not_echo_secrets_or_arbitrary_metadata(self):
        payload = {"application": {"_id": check.APP_ID, "appName": TOKEN,
            "teamId": TOKEN, "email": TOKEN, "environment": {"privateKey": TOKEN},
            "branches": [TOKEN, "atodeyarubox-build"]}}
        result = check.read_application(TOKEN, self.response(payload))
        self.assertNotIn(TOKEN, json.dumps(result))
        self.assertTrue(result["original_work_branch_listed"])
        self.assertFalse(result["team_scope_verified"])

    def test_http_error_body_and_exception_never_escape(self):
        opener = Mock()
        opener.open.side_effect = urllib.error.HTTPError(check.ENDPOINT, 403, TOKEN, {}, io.BytesIO(TOKEN.encode()))
        result = check.read_application(TOKEN, opener)
        self.assertEqual(result["http_status"], 403)
        self.assertNotIn(TOKEN, json.dumps(result))

    def test_network_error_never_echoes_token(self):
        opener = Mock()
        opener.open.side_effect = urllib.error.URLError(TOKEN)
        result = check.read_application(TOKEN, opener)
        self.assertEqual(result["status"], "CODEMAGIC_NETWORK_UNAVAILABLE")
        self.assertNotIn(TOKEN, json.dumps(result))

    def test_unexpected_transport_error_never_echoes_token(self):
        opener = Mock()
        opener.open.side_effect = RuntimeError(TOKEN)
        result = check.read_application(TOKEN, opener)
        self.assertEqual(result["status"], "CODEMAGIC_READ_UNAVAILABLE")
        self.assertNotIn(TOKEN, json.dumps(result))

    def test_authenticated_redirect_is_refused(self):
        handler = check.NoRedirect()
        with self.assertRaises(check.RefusedRedirect):
            handler.redirect_request(None, None, 302, TOKEN, {}, "https://external.invalid/")
        opener = Mock()
        opener.open.side_effect = check.RefusedRedirect()
        self.assertEqual(check.read_application(TOKEN, opener)["status"], "AUTHENTICATED_REDIRECT_REFUSED")

    def test_large_response_rejected(self):
        result = check.read_application(TOKEN, self.response(b"x" * (check.LIMIT + 1)))
        self.assertEqual(result["status"], "RESPONSE_LIMIT_EXCEEDED")

    def test_invalid_json_and_shape_fail_closed(self):
        for payload in (b"invalid", [], {"application": []}):
            self.assertNotEqual(check.read_application(TOKEN, self.response(payload))["status"],
                                "APP_METADATA_READ_AUTHENTICATED")

    def test_missing_token_invalidates_old_pass_and_prints_no_secrets(self):
        with tempfile.TemporaryDirectory() as folder:
            report = Path(folder) / "report.json"
            report.write_text('{"status":"APP_METADATA_READ_AUTHENTICATED"}')
            output = io.StringIO()
            with patch.object(check, "REPORT", report), patch.dict(check.os.environ, {}, clear=True), contextlib.redirect_stdout(output):
                self.assertEqual(check.main(), 1)
            self.assertEqual(json.loads(report.read_text())["status"], "CODEMAGIC_TOKEN_MISSING")
            self.assertEqual(output.getvalue().strip(), "CODEMAGIC_TOKEN_MISSING")


if __name__ == "__main__":
    unittest.main()
