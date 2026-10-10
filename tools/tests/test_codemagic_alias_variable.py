import io
import json
import unittest
from tools import codemagic_alias_variable as m

TOKEN = "synthetic-token-not-a-real-credential"
ID = "3" * 24
GATE = {"status": "APP_INTEGRATION_METADATA_READ", "app_owner_verified": True,
        "personal_context_owns_app": True, "free_allowance_verified": True,
        "paid_cicd_subscription_present": False, "free_m2_remaining_seconds": 6000,
        "normalized_alias_codepoints": list(map(ord, m.VALUE))}


class Transport:
    def __init__(self, responses):
        self.responses, self.requests = iter(responses), []
    def open(self, request, timeout):
        self.requests.append(request)
        value = next(self.responses)
        if isinstance(value, Exception):
            raise value
        return io.BytesIO(json.dumps(value).encode())


def responses():
    return [{"data": [], "total_pages": 1}, {"data": {"id": ID, "name": m.GROUP}},
            {"data": []}, {}, {"data": [{"name": m.NAME, "secure": True, "value": TOKEN}]}]


class Checks(unittest.TestCase):
    def test_gate_blocks_all_requests(self):
        for key, value in (("app_owner_verified", False), ("personal_context_owns_app", False),
                           ("free_allowance_verified", False), ("paid_cicd_subscription_present", True),
                           ("free_m2_remaining_seconds", 0), ("normalized_alias_codepoints", [])):
            t = Transport([])
            m.configure(TOKEN, t, {**GATE, key: value})
            self.assertEqual(t.requests, [])

    def test_exact_app_and_created_group_only(self):
        t = Transport(responses())
        result = m.configure(TOKEN, t, GATE)
        self.assertEqual(result["status"], "APP_LOCAL_ENCRYPTED_ALIAS_CONFIGURED")
        self.assertEqual([r.method for r in t.requests], ["GET", "POST", "GET", "POST", "GET"])
        self.assertTrue(all(r.full_url in (m.BASE + m.APP_PATH, m.BASE + "/variable-groups/" + ID + "/variables") for r in t.requests))
        self.assertEqual(json.loads(t.requests[3].data), {"secure": True, "variables": [{"name": m.NAME, "value": m.VALUE}]})
        self.assertNotIn(TOKEN, json.dumps(result))

    def test_existing_group_not_modified(self):
        t = Transport([{"data": [{"id": ID, "name": m.GROUP}]}])
        self.assertEqual(m.configure(TOKEN, t, GATE)["diagnostic"], "EXISTING_GROUP_NOT_MODIFIED")
        self.assertEqual(len(t.requests), 1)

    def test_empty_zero_page_response_is_supported(self):
        values = responses()
        values[0] = {"data": [], "total_pages": 0, "current_page": 1}
        values[2] = {"data": [], "total_pages": 0, "current_page": 1}
        result = m.configure(TOKEN, Transport(values), GATE)
        self.assertEqual(result["status"], "APP_LOCAL_ENCRYPTED_ALIAS_CONFIGURED")
        self.assertEqual(result["free_m2_remaining_seconds"], 6000)

    def test_inconsistent_or_incomplete_pages_cannot_mutate(self):
        for data, pages, current in (([{"name": "other"}], 0, 1), ([], 2, 1), ([], 1, 2),
                                     ([], True, 1), ([], 1, True)):
            t = Transport([{"data": data, "total_pages": pages, "current_page": current}])
            result = m.configure(TOKEN, t, GATE)
            self.assertEqual(result["diagnostic"], "APP_GROUP_LIST_UNVERIFIED")
            self.assertEqual([r.method for r in t.requests], ["GET"])

    def test_page_diagnostics_never_copy_arbitrary_values(self):
        result = m.configure(TOKEN, Transport([{"data": TOKEN, "total_pages": TOKEN}]), GATE)
        self.assertNotIn(TOKEN, json.dumps(result))

    def test_group_identity_required_before_variable_import(self):
        t = Transport([{"data": []}, {"data": {"id": "../user", "name": m.GROUP}}])
        self.assertEqual(m.configure(TOKEN, t, GATE)["diagnostic"], "GROUP_CREATION_OUTCOME_UNVERIFIED")
        self.assertEqual(len(t.requests), 2)

    def test_nonempty_group_never_overwritten(self):
        t = Transport(responses()[:2] + [{"data": [{"name": "other"}]}])
        self.assertEqual(m.configure(TOKEN, t, GATE)["diagnostic"], "NEW_GROUP_NOT_EMPTY")
        self.assertEqual(len(t.requests), 3)

    def test_timeout_is_reserved_and_never_retried(self):
        checkpoints = []
        t = Transport([{"data": []}, TimeoutError(TOKEN)])
        result = m.configure(TOKEN, t, GATE, checkpoints.append)
        self.assertEqual(len(t.requests), 2)
        self.assertEqual(checkpoints[0]["status"], "MUTATION_RESERVED_OUTCOME_UNKNOWN")
        self.assertNotIn(TOKEN, json.dumps(result))

    def test_plaintext_metadata_does_not_pass(self):
        t = Transport(responses()[:4] + [{"data": [{"name": m.NAME, "secure": False}]}])
        self.assertEqual(m.configure(TOKEN, t, GATE)["diagnostic"], "ENCRYPTED_VARIABLE_METADATA_UNVERIFIED")


if __name__ == "__main__":
    unittest.main()
