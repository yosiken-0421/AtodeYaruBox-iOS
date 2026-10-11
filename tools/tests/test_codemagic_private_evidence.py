import base64
import contextlib
import io
import json
import os
import unittest
from unittest.mock import patch
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding,rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from tools import codemagic_private_evidence as m
SOURCE='a'*40
PRIVATE='synthetic private account result'
class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.key=rsa.generate_private_key(public_exponent=65537,key_size=3072)
    def decode(self,p,source=SOURCE):
        secret=self.key.decrypt(base64.b64decode(p['wrapped_key']),padding.OAEP(mgf=padding.MGF1(hashes.SHA256()),algorithm=hashes.SHA256(),label=None))
        return AESGCM(secret).decrypt(base64.b64decode(p['nonce']),base64.b64decode(p['ciphertext']),m.CONTEXT+source.encode())
    def test_private_result_is_encrypted_and_size_does_not_reveal_content(self):
        p=m.seal({'private':PRIVATE},self.key.public_key(),SOURCE)
        self.assertNotIn(PRIVATE,json.dumps(p));self.assertNotIn('private',p)
        self.assertEqual(json.loads(self.decode(p)),{'private':PRIVATE})
        self.assertEqual(len(base64.b64decode(p['ciphertext'])),4112)
        q=m.seal({'private':'x'},self.key.public_key(),SOURCE)
        self.assertEqual(len(p['ciphertext']),len(q['ciphertext']));self.assertNotEqual(p['nonce'],q['nonce'])
    def test_wrong_context_or_changed_ciphertext_cannot_be_decrypted(self):
        p=m.seal({'private':PRIVATE},self.key.public_key(),SOURCE)
        with self.assertRaises(InvalidTag):self.decode(p,'b'*40)
        raw=bytearray(base64.b64decode(p['ciphertext']));raw[0]^=1;p['ciphertext']=base64.b64encode(raw).decode()
        with self.assertRaises(InvalidTag):self.decode(p)
    def test_main_never_writes_plain_report_or_logs_private_result(self):
        output=io.StringIO()
        with patch.dict(os.environ,{'GITHUB_SHA':SOURCE,'CODEMAGIC_API_TOKEN':'synthetic'}),patch.object(m,'public_key',return_value=self.key.public_key()),patch.object(m.evidence,'inspect',return_value={'private':PRIVATE}),patch.object(m.evidence,'write_report',side_effect=AssertionError()),contextlib.redirect_stdout(output):
            self.assertEqual(m.main(),0)
        self.assertNotIn(PRIVATE,output.getvalue())
        self.assertEqual(json.loads(self.decode(json.loads(output.getvalue())))['private'],PRIVATE)
    def test_failure_logs_no_api_message_or_secret(self):
        output=io.StringIO()
        with patch.object(m.evidence,'inspect',side_effect=RuntimeError(PRIVATE)),contextlib.redirect_stdout(output):self.assertEqual(m.main(),1)
        self.assertEqual(output.getvalue().strip(),'PRIVATE_EVIDENCE_UNAVAILABLE')
if __name__=='__main__':unittest.main()
