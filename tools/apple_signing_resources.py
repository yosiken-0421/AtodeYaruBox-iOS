"""Prepare only the app's three IDs and one reusable matching signing certificate."""
import base64
from datetime import datetime, timezone
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

from tools.apple_signing_preflight import IDENTIFIERS, CheckError, NoRedirect, token_from_environment, rows, exact_bundle_rows

BASE = 'https://api.appstoreconnect.apple.com'
LIMIT = 1024 * 1024


def resource_token(environment):
    import jwt
    def encode(payload, key, **options):
        # Apple supports scope for GET requests only. The client below limits
        # POST bodies to the three task IDs and this persistent signing key's CSR.
        payload = {k: v for k, v in payload.items() if k != 'scope'}
        return jwt.encode(payload, key, **options)
    return token_from_environment(environment, encode)


class Client:
    def __init__(self, token, csr, opener=None, checkpoint=None):
        self.token, self.csr = token, csr
        self.opener = opener or urllib.request.build_opener(NoRedirect())
        self.checkpoint = checkpoint

    def request(self, route, method='GET', query=None, body=None):
        allowed = False
        if route == '/v1/bundleIds':
            allowed = (method == 'GET' and isinstance(query, dict) and query == {'filter[identifier]': query.get('filter[identifier]'),
                'fields[bundleIds]': 'identifier,platform,seedId', 'limit': 200}
                and query['filter[identifier]'] in IDENTIFIERS)
            if method == 'POST' and isinstance(body, dict):
                data = body.get('data', {})
                identifier = data.get('attributes', {}).get('identifier')
                allowed = identifier in IDENTIFIERS and body == bundle_body(identifier)
        elif route == '/v1/certificates':
            allowed = method == 'GET' and query == certificate_query()
            if method == 'POST':
                allowed = body == {'data': {'type': 'certificates', 'attributes': {
                    'certificateType': 'DISTRIBUTION', 'csrContent': self.csr}}}
        if not allowed:
            raise CheckError('UNAPPROVED_RESOURCE_REQUEST')
        if method == 'POST' and self.checkpoint:
            self.checkpoint('BUNDLE_ID_POST_RESERVED' if route == '/v1/bundleIds' else 'CERTIFICATE_POST_RESERVED')
        url = BASE + route + ('?' + urllib.parse.urlencode(query) if query else '')
        req = urllib.request.Request(url, method=method,
            data=None if body is None else json.dumps(body).encode(), headers={
                'Authorization': 'Bearer ' + self.token, 'Content-Type': 'application/json'})
        try:
            with self.opener.open(req, timeout=20) as response:
                raw = response.read(LIMIT + 1)
            if len(raw) > LIMIT:
                raise CheckError('RESOURCE_RESPONSE_LIMIT')
            return json.loads(raw)
        except urllib.error.HTTPError as error:
            raise CheckError('RESOURCE_HTTP_' + str(int(error.code))) from None
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            raise CheckError('RESOURCE_REQUEST_OUTCOME_UNAVAILABLE') from None


def bundle_body(identifier):
    if identifier not in IDENTIFIERS:
        raise CheckError('UNAPPROVED_IDENTIFIER')
    names = dict(zip(IDENTIFIERS, ('AtodeYaruBox', 'AtodeYaruBox Share', 'AtodeYaruBox Widgets')))
    return {'data': {'type': 'bundleIds', 'attributes': {'identifier': identifier,
                'name': names[identifier], 'platform': 'IOS'}}}


def certificate_query():
    return {'filter[certificateType]': 'DISTRIBUTION,IOS_DISTRIBUTION',
            'fields[certificates]': 'certificateType,certificateContent,expirationDate', 'limit': 200}


def load_key(value):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    try:
        if not isinstance(value, str) or len(value) > 8192:
            raise ValueError()
        key = serialization.load_pem_private_key(value.encode(), password=None)
        if not isinstance(key, rsa.RSAPrivateKey) or key.key_size != 2048:
            raise ValueError()
        return key
    except Exception:
        raise CheckError('CERTIFICATE_KEY_INVALID') from None


def prepare(environment, checkpoint=None, allow_create=True):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.x509.oid import NameOID
    key = load_key(environment.get('CERTIFICATE_PRIVATE_KEY', ''))
    csr = x509.CertificateSigningRequestBuilder().subject_name(
        x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'AtodeYaruBox CI')])).sign(key, hashes.SHA256())
    csr_text = csr.public_bytes(serialization.Encoding.PEM).decode('ascii')
    client = Client(resource_token(environment), csr_text, checkpoint=checkpoint)
    resources_created = []
    for identifier in IDENTIFIERS:
        entries = exact_bundle_rows(rows(client.request('/v1/bundleIds', query={'filter[identifier]': identifier,
                       'fields[bundleIds]': 'identifier,platform,seedId', 'limit': 200})), identifier)
        if not entries:
            if not allow_create:
                raise CheckError('EXISTING_SIGNING_RESOURCES_REQUIRED')
            created = client.request('/v1/bundleIds', 'POST', body=bundle_body(identifier)).get('data', {})
            if created.get('attributes', {}).get('identifier') != identifier:
                raise CheckError('BUNDLE_CREATION_OUTCOME_UNVERIFIED')
            resources_created.append(identifier)
    entries = rows(client.request('/v1/certificates', query=certificate_query()))
    if any(e['attributes'].get('certificateType') not in ('DISTRIBUTION', 'IOS_DISTRIBUTION') for e in entries):
        raise CheckError('CERTIFICATE_RESPONSE_INVALID')
    matching = []
    public = key.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    for entry in entries:
        try:
            cert = x509.load_der_x509_certificate(base64.b64decode(entry['attributes']['certificateContent'], validate=True))
            if cert.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo) == public:
                matching.append(cert)
        except Exception:
            raise CheckError('CERTIFICATE_CONTENT_UNVERIFIED') from None
    if len(matching) > 1:
        raise CheckError('MATCHING_CERTIFICATE_AMBIGUOUS')
    certificate_created = False
    if not matching:
        if not allow_create:
            raise CheckError('EXISTING_SIGNING_RESOURCES_REQUIRED')
        if len(entries) >= 3:
            raise CheckError('DISTRIBUTION_CERTIFICATE_LIMIT_NO_REVOCATION')
        response = client.request('/v1/certificates', 'POST', body={'data': {'type': 'certificates',
                    'attributes': {'certificateType': 'DISTRIBUTION', 'csrContent': csr_text}}})
        try:
            cert = x509.load_der_x509_certificate(base64.b64decode(response['data']['attributes']['certificateContent'], validate=True))
            if cert.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo) != public:
                raise ValueError()
        except Exception:
            raise CheckError('CERTIFICATE_CREATION_OUTCOME_UNVERIFIED') from None
        matching = [cert]
        certificate_created = True
    cert = matching[0]
    if cert.not_valid_after_utc <= datetime.now(timezone.utc):
        raise CheckError('MATCHING_CERTIFICATE_EXPIRED')
    teams = cert.subject.get_attributes_for_oid(NameOID.ORGANIZATIONAL_UNIT_NAME)
    if len(teams) != 1 or not re.fullmatch(r'[A-Z0-9]{10}', teams[0].value):
        raise CheckError('CERTIFICATE_TEAM_UNVERIFIED')
    return key, cert, teams[0].value, {'bundle_ids_created': resources_created,
            'all_three_bundle_ids_available': True, 'distribution_certificate_created': certificate_created,
            'matching_certificate_key_verified': True, 'team_identifier_verified': True}
