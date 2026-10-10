import io
import json
import unittest
from tools import codemagic_signing_key as m

TOKEN = 'synthetic-token-not-a-real-credential'
KEY = '-----BEGIN PRIVATE KEY-----\n' + 'SYNTHETIC_BODY_' * 24 + '\n-----END PRIVATE KEY-----'
GROUP_ID = '1' * 24


def gate():
    return dict(status='APP_INTEGRATION_METADATA_READ', app_owner_verified=True,
                personal_context_owns_app=True, free_allowance_verified=True,
                paid_cicd_subscription_present=False, free_m2_remaining_seconds=4000,
                expected_alias_normalized=True, expected_alias_ambiguous=False)


def page(rows):
    return dict(data=rows, total_pages=1 if rows else 0, current_page=1)


class Transport:
    def __init__(self, rows):
        self.rows, self.requests = list(rows), []
    def open(self, request, timeout):
        self.requests.append(request)
        row = self.rows.pop(0)
        if isinstance(row, Exception):
            raise row
        return io.BytesIO(json.dumps(row).encode())


class Tests(unittest.TestCase):
    def test_new_key_reaches_only_encrypted_task_variable_and_never_report(self):
        t = Transport([page([]), {'data': {'name': m.GROUP, 'id': GROUP_ID}}, page([]), [],
                       page([{'name': m.NAME, 'secure': True, 'value': KEY}])])
        checkpoints = []
        r = m.configure(TOKEN, t, gate(), checkpoints.append, factory=lambda: KEY)
        self.assertEqual(r['status'], 'ENCRYPTED_SIGNING_KEY_CONFIGURED')
        posts = [x for x in t.requests if x.method == 'POST']
        self.assertEqual(len(posts), 2)
        self.assertEqual(posts[1].full_url, m.BASE + '/variable-groups/' + GROUP_ID + '/variables')
        self.assertEqual(json.loads(posts[1].data), {'secure': True, 'variables': [{'name': m.NAME, 'value': KEY}]})
        self.assertNotIn(KEY, json.dumps([r, checkpoints]))
        self.assertNotIn(TOKEN, json.dumps([r, checkpoints]))
        self.assertFalse(r['apple_resources_modified'])

    def test_failed_owner_cost_or_alias_gate_never_generates_or_writes(self):
        for field, value in (('app_owner_verified', False), ('free_m2_remaining_seconds', 1799),
                             ('paid_cicd_subscription_present', True), ('expected_alias_ambiguous', True)):
            t = Transport([])
            r = m.configure(TOKEN, t, {**gate(), field: value}, factory=lambda: self.fail('Must not generate'))
            self.assertEqual(r['status'], 'CURRENT_OWNER_ALIAS_AND_FREE_ALLOWANCE_REQUIRED')
            self.assertEqual(t.requests, [])

    def test_existing_encrypted_variable_is_read_without_overwrite(self):
        t = Transport([page([{'name': m.GROUP, 'id': GROUP_ID}]), page([{'name': m.NAME, 'secure': True}])])
        r = m.configure(TOKEN, t, gate(), factory=lambda: self.fail('Do not replace an existing key'))
        self.assertEqual(r['status'], 'ENCRYPTED_SIGNING_KEY_METADATA_VERIFIED')
        self.assertTrue(all(x.method == 'GET' for x in t.requests))

    def test_uncertain_import_is_not_repeated_and_never_leaks(self):
        t = Transport([page([]), {'data': {'name': m.GROUP, 'id': GROUP_ID}}, page([]), OSError(KEY)])
        r = m.configure(TOKEN, t, gate(), factory=lambda: KEY)
        self.assertEqual(r['diagnostic'], 'REQUEST_OUTCOME_UNAVAILABLE')
        self.assertEqual(len([x for x in t.requests if x.method == 'POST']), 2)
        self.assertNotIn(KEY, json.dumps(r))

    def test_unencrypted_existing_variable_is_refused(self):
        t = Transport([page([{'name': m.GROUP, 'id': GROUP_ID}]), page([{'name': m.NAME, 'secure': False}])])
        r = m.configure(TOKEN, t, gate())
        self.assertEqual(r['diagnostic'], 'EXISTING_VARIABLE_UNVERIFIED_NO_OVERWRITE')
        self.assertTrue(all(x.method == 'GET' for x in t.requests))

    def test_actual_generated_key_is_rsa_2048(self):
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        key = serialization.load_pem_private_key(m.make_key().encode(), password=None)
        self.assertIsInstance(key, rsa.RSAPrivateKey)
        self.assertEqual(key.key_size, 2048)


if __name__ == '__main__':
    unittest.main()
