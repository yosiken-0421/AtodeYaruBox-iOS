import io
import json
import unittest
from tools import codemagic_apple_evidence as m

TOKEN = "synthetic-token-not-a-real-credential"
URL = "https://storage.googleapis.com/synthetic/" + m.NAME


class Transport:
    def __init__(self, value):
        self.value, self.requests = value, []
    def open(self, request, timeout):
        self.requests.append(request)
        return io.BytesIO(json.dumps(self.value).encode())


def report():
    return dict(status="NOT_VERIFIED", authentication_verified=False, signed_build_ready=False,
                apple_resources_modified=False, binary_uploaded=False, new_payment_enabled=False,
                diagnostic="INTEGRATION_CREDENTIALS_MISSING")


def build():
    return {"data": dict(id=m.BUILD, app_id=m.APP_ID, branch=m.BRANCH, commit={"hash": m.COMMIT},
        status="failed", artifacts=[{"name": m.NAME, "short_lived_download_url": URL}])}


class Checks(unittest.TestCase):
    def test_reads_one_known_report_without_forwarding_credentials(self):
        api, storage = Transport(build()), Transport({**report(), "private": TOKEN})
        result = m.inspect(TOKEN, api, storage)
        self.assertEqual(result["status"], "KNOWN_APPLE_REPORT_READ")
        self.assertEqual([r.method for r in api.requests + storage.requests], ["GET", "GET"])
        self.assertEqual(api.requests[0].full_url, m.API)
        self.assertNotIn("X-auth-token", storage.requests[0].headers)
        self.assertNotIn(TOKEN, json.dumps(result))

        passed = m.log_diagnostic(b"Ran 18 tests in 0.2s\n\nOK\n")
        self.assertTrue(passed["unit_checks_passed"])
        self.assertFalse(m.log_diagnostic(b"Ran 13 tests in 0.2s\n\nOK\n")["unit_checks_passed"])
        self.assertNotIn(URL, json.dumps(result))

    def test_identity_mismatch_never_downloads(self):
        for key, value in (("id", "0"*24), ("app_id", "0"*24), ("branch", "main"), ("commit", {"hash": "0"*40})):
            b = build()
            b["data"][key] = value
            storage = Transport({})
            self.assertEqual(m.inspect(TOKEN, Transport(b), storage)["diagnostic"], "BUILD_IDENTITY_UNVERIFIED")
            self.assertEqual(storage.requests, [])

    def test_unknown_download_destinations_are_refused(self):
        for url in ("https://evil.example/"+m.NAME, "http://storage.googleapis.com/"+m.NAME,
                    "https://api.codemagic.io@evil.example/"+m.NAME, "https://api.codemagic.io/secret.p8"):
            self.assertFalse(m.allowed_download(url))

    def test_arbitrary_diagnostics_or_resource_writes_are_refused(self):
        self.assertIsNone(m.sanitize({**report(), "diagnostic": TOKEN}))
        self.assertIsNone(m.sanitize({**report(), "binary_uploaded": True}))
        self.assertIsNone(m.sanitize({**report(), "authentication_verified": True}))

    def test_authenticated_report_requires_exact_known_identifiers(self):
        good = {**report(), "status": "APPLE_READ_AUTHENTICATED", "authentication_verified": True,
                "bundle_identifiers": {i:"NOT_REGISTERED" for i in m.IDS}, "distribution_certificates_returned": 2}
        good.pop("diagnostic")
        self.assertEqual(m.sanitize(good), good)
        self.assertIsNone(m.sanitize({**good, "bundle_identifiers": {"other":"EXISTS"}}))

    def test_log_diagnostics_never_copy_log_text_or_private_values(self):
        result = m.log_diagnostic((TOKEN + "\nModuleNotFoundError\nFAILED (errors=1)\n" + json.dumps(report())).encode())
        self.assertTrue(result["python_module_missing"])
        self.assertTrue(result["unit_checks_failed"])
        self.assertEqual(result["apple_report"], report())
        self.assertNotIn(TOKEN, json.dumps(result))


if __name__ == "__main__":
    unittest.main()
