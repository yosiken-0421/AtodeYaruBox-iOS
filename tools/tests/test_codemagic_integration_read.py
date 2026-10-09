import io
import json
import unittest
import urllib.error

from tools import codemagic_integration_read as m

TOKEN = "synthetic-test-token-no-real-credential"
OWNER = "1" * 24
OTHER = "2" * 24


class Response(io.BytesIO):
    def __init__(self, payload):
        super().__init__(json.dumps(payload).encode())


class Transport:
    def __init__(self, user=None, app=None, build=None, team=None, failure=None):
        self.requests = []
        self.payloads = {"/apps/" + m.APP_ID: {"application": app if app is not None else {"_id": m.APP_ID, "ownerTeam": OWNER}},
                         "/user": {"user": user if user is not None else {"ok": True, "activeTeam": OWNER,
                            "appStoreConnectIntegration": {"isEnabled": True, "apiKeys": [{"name": m.ALIAS, "keyId": "fake"}]}}},
                         "/builds/" + m.BUILD_ID: build or {}, "/team/" + OWNER: {"team": team or {}}}
        self.failure = failure

    def open(self, request, timeout):
        self.requests.append(request)
        if self.failure:
            raise self.failure
        return Response(self.payloads[request.full_url.removeprefix("https://api.codemagic.io")])


class Checks(unittest.TestCase):
    def test_invalid_credential_never_sent(self):
        transport = Transport()
        self.assertEqual(m.inspect("bad", transport)["status"], "CODEMAGIC_TOKEN_INVALID")
        self.assertEqual(transport.requests, [])

    def test_personal_owner_reads_only_target_and_owner_context(self):
        transport = Transport()
        result = m.inspect(TOKEN, transport)
        self.assertTrue(result["personal_context_owns_app"])
        self.assertTrue(result["expected_alias_exact"])
        self.assertFalse(result["apple_authentication_verified"])
        self.assertEqual([r.full_url for r in transport.requests], ["https://api.codemagic.io/apps/" + m.APP_ID, "https://api.codemagic.io/user"])
        self.assertTrue(all(r.method == "GET" for r in transport.requests))

    def test_no_owner_no_account_read(self):
        transport = Transport(app={"_id": m.APP_ID})
        result = m.inspect(TOKEN, transport)
        self.assertEqual(result["failed_stage"], "KNOWN_BUILD_IDENTITY")
        self.assertFalse(any(r.full_url.endswith("/user") for r in transport.requests))

    def test_known_build_proves_app_owner(self):
        transport = Transport(app={"_id": m.APP_ID}, build={"application": {"_id": m.APP_ID, "ownerTeam": OWNER}, "build": {"_id": m.BUILD_ID}})
        self.assertTrue(m.inspect(TOKEN, transport)["app_owner_verified"])

    def test_wrong_app_stops_before_context(self):
        transport = Transport(app={"_id": "wrong", "ownerTeam": OWNER})
        self.assertEqual(m.inspect(TOKEN, transport)["failed_stage"], "APP_IDENTITY")
        self.assertEqual(len(transport.requests), 1)

    def test_untrusted_owner_path_never_requested(self):
        transport = Transport(app={"_id": m.APP_ID, "ownerTeam": "../user/api-key"})
        m.inspect(TOKEN, transport)
        self.assertFalse(any("/team/" in r.full_url for r in transport.requests))

    def test_only_target_app_team_requested(self):
        user = {"ok": True, "activeTeam": OTHER}
        transport = Transport(user=user, team={"_id": OWNER, "appStoreConnectIntegration": {"apiKeys": [{"name": m.ALIAS}]}})
        result = m.inspect(TOKEN, transport)
        self.assertFalse(result["personal_context_owns_app"])
        self.assertTrue(result["expected_alias_exact"])
        self.assertEqual(transport.requests[-1].full_url, "https://api.codemagic.io/team/" + OWNER)

    def test_unknown_team_not_trusted(self):
        transport = Transport(user={"ok": True, "activeTeam": OTHER}, team={"_id": OTHER})
        self.assertEqual(m.inspect(TOKEN, transport)["failed_stage"], "APP_TEAM_IDENTITY")

    def test_arbitrary_credentials_and_details_not_returned(self):
        transport = Transport(user={"ok": True, "activeTeam": OWNER, "email": TOKEN,
            "appStoreConnectIntegration": {"apiKeys": [{"name": m.ALIAS, "keyId": TOKEN, "privateKey": TOKEN}]}})
        report = json.dumps(m.inspect(TOKEN, transport))
        self.assertNotIn(TOKEN, report)
        self.assertNotIn(OWNER, report)

    def test_normalization_does_not_claim_exact_match(self):
        meta = m.alias_metadata({"appStoreConnectIntegration": {"apiKeys": [{"name": " " + m.ALIAS + " "}]}})
        self.assertTrue(meta["expected_alias_normalized"])
        self.assertFalse(meta["expected_alias_exact"])

    def test_only_proven_known_alias_spelling_is_returned(self):
        for name in (" " + m.ALIAS + " ", "ＡｔｏｄｅＹａｒｕＢｏｘ－ＣＩ"):
            result = m.alias_metadata({"appStoreConnectIntegration": {"apiKeys": [{"name": name}]}})
            self.assertEqual("".join(map(chr, result["normalized_alias_codepoints"])), name)
        for name in (TOKEN, m.ALIAS + "\n", " " * 65 + m.ALIAS):
            result = m.alias_metadata({"appStoreConnectIntegration": {"apiKeys": [{"name": name}]}})
            self.assertNotIn("normalized_alias_codepoints", result)

    def test_exception_data_never_printed(self):
        for error in (m.RefusedRedirect(), TimeoutError(TOKEN), RuntimeError(TOKEN),
                      urllib.error.HTTPError("https://example.com", 403, TOKEN, {}, io.BytesIO(TOKEN.encode()))):
            result = m.inspect(TOKEN, Transport(failure=error))
            self.assertEqual(result["status"], "CONTEXT_READ_UNAVAILABLE")
            self.assertNotIn(TOKEN, json.dumps(result))


if __name__ == "__main__":
    unittest.main()
