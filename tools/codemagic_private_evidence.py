"""Return fixed-size encrypted evidence; no account result is logged or saved."""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from tools import codemagic_signed_evidence as evidence

PUBLIC_KEY=Path(__file__).with_name('owner_evidence_public.pem')
CONTEXT=b'AtodeYaruBox private CI evidence v1:'

def public_key():
    key=serialization.load_pem_public_key(PUBLIC_KEY.read_bytes())
    if not isinstance(key,rsa.RSAPublicKey) or key.key_size<3072:
        raise ValueError('Unsupported public key')
    return key

def seal(result,key,source):
    if not re.fullmatch('[0-9a-f]{40}',source):raise ValueError('Source required')
    plain=json.dumps(result,separators=(',',':')).encode('utf-8')
    if len(plain)>4096:raise ValueError('Evidence exceeds limit')
    secret=AESGCM.generate_key(bit_length=256);nonce=os.urandom(12)
    encrypted=AESGCM(secret).encrypt(nonce,plain.ljust(4096,b' '),CONTEXT+source.encode())
    wrapped=key.encrypt(secret,padding.OAEP(mgf=padding.MGF1(hashes.SHA256()),algorithm=hashes.SHA256(),label=None))
    der=key.public_bytes(serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo)
    encode=lambda value:base64.b64encode(value).decode('ascii')
    return dict(status='PRIVATE_EVIDENCE_ENCRYPTED',source_commit=source,key_fingerprint=hashlib.sha256(der).hexdigest(),
                wrapped_key=encode(wrapped),nonce=encode(nonce),ciphertext=encode(encrypted))

def main():
    try:
        source=os.environ.get('GITHUB_SHA','')
        result=evidence.inspect(os.environ.pop('CODEMAGIC_API_TOKEN',''))
        result['source_commit']=source
        envelope=seal(result,public_key(),source)
    except Exception:
        # Do not print exceptions, account data, API messages, or credentials.
        print('PRIVATE_EVIDENCE_UNAVAILABLE');return 1
    print(json.dumps(envelope));return 0

if __name__=='__main__':raise SystemExit(main())
