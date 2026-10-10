"""Read-only Apple API check; private keys and bearer tokens never leave memory."""
from datetime import datetime, timezone
import base64
import json
import os
from pathlib import Path
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]
IDENTIFIERS = ('jp.atodeyarubox.app', 'jp.atodeyarubox.app.share',
               'jp.atodeyarubox.app.widgets')
ALLOWED_ROUTES = ('/v1/bundleIds', '/v1/certificates')
LIMIT_BYTES = 1024 * 1024


class CheckError(RuntimeError):
    """Only predefined, non-secret diagnostic codes may be reported."""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise CheckError('REDIRECT_REFUSED')


def normalize_private_key(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 16 * 1024:
        raise CheckError('PRIVATE_KEY_FORMAT_INVALID')
    key = value.lstrip('\ufeff').strip().replace('\r\n', '\n')
    kind = 'PEM'
    if key.startswith('@file:'):
        candidate = Path(key[6:]).expanduser().resolve()
        roots = [Path('/tmp').resolve(), ROOT.resolve()]
        if (candidate.suffix.lower() != '.p8' or not any(candidate.is_relative_to(root) for root in roots)
                or not candidate.is_file() or candidate.stat().st_size > 16 * 1024):
            raise CheckError('PRIVATE_KEY_REFERENCE_REFUSED')
        try:
            key = candidate.read_text(encoding='utf-8-sig').strip().replace('\r\n', '\n')
        except (OSError, UnicodeError):
            raise CheckError('PRIVATE_KEY_REFERENCE_UNAVAILABLE') from None
        kind = 'FILE_REFERENCE'
    elif '\\n' in key and '\n' not in key and key.startswith('-----BEGIN PRIVATE KEY-----'):
        key = key.replace('\\r\\n', '\n').replace('\\n', '\n')
        kind = 'ESCAPED_PEM'
    elif not key.startswith('-----BEGIN PRIVATE KEY-----'):
        try:
            key = base64.b64decode(key, validate=True).decode('utf-8').strip()
        except (ValueError, UnicodeError):
            raise CheckError('PRIVATE_KEY_FORMAT_INVALID') from None
        kind = 'BASE64_PEM'
    if (not key.startswith('-----BEGIN PRIVATE KEY-----\n') or not key.endswith('\n-----END PRIVATE KEY-----')
            or len(key) > 16 * 1024):
        raise CheckError('PRIVATE_KEY_FORMAT_INVALID')
    return key, kind


def token_from_environment(environment, encoder=None, now=None):
    names = ('APP_STORE_CONNECT_KEY_IDENTIFIER', 'APP_STORE_CONNECT_ISSUER_ID',
             'APP_STORE_CONNECT_PRIVATE_KEY')
    values = [environment.get(name, '') for name in names]
    if not all(isinstance(value, str) and value.strip() for value in values):
        raise CheckError('INTEGRATION_CREDENTIALS_MISSING')
    key_id, issuer, private_key = values
    if (not re.fullmatch(r'[A-Z0-9]{10}', key_id)
            or len(private_key) > 16 * 1024):
        raise CheckError('INTEGRATION_CREDENTIALS_INVALID')
    try:
        uuid.UUID(issuer)
    except (ValueError, AttributeError):
        raise CheckError('INTEGRATION_CREDENTIALS_INVALID') from None
    private_key, key_kind = normalize_private_key(private_key)
    if encoder is None:
        try:
            import jwt
            encoder = jwt.encode
        except ImportError:
            raise CheckError('JWT_DEPENDENCY_MISSING') from None
    issued = int(time.time() if now is None else now)
    try:
        return encoder({'iss': issuer, 'iat': issued, 'exp': issued + 300,
                        'aud': 'appstoreconnect-v1',
                        'scope': ['GET ' + route for route in ALLOWED_ROUTES]},
                       private_key, algorithm='ES256',
                       headers={'kid': key_id, 'typ': 'JWT'})
    except Exception as error:
        # Signing libraries can include key contents in exceptions. Never emit them.
        failure = CheckError('JWT_SIGNING_FAILED')
        failure.key_kind = key_kind
        failure.signing_error_kind = {
            'ValueError': 'VALUE_ERROR', 'InvalidKeyError': 'INVALID_KEY',
            'UnsupportedAlgorithm': 'UNSUPPORTED_ALGORITHM', 'ImportError': 'IMPORT_ERROR',
            'NotImplementedError': 'NOT_IMPLEMENTED',
        }.get(type(error).__name__, 'UNKNOWN')
        raise failure from None


class AppleReader:
    def __init__(self, token, opener=None):
        self.token = token
        self.opener = opener or urllib.request.build_opener(NoRedirect())

    def get(self, route, query):
        if route not in ALLOWED_ROUTES:
            raise CheckError('UNAPPROVED_ROUTE')
        if route == '/v1/bundleIds':
            if query.get('filter[identifier]') not in IDENTIFIERS:
                raise CheckError('UNAPPROVED_IDENTIFIER')
        elif query.get('filter[certificateType]') != 'DISTRIBUTION,IOS_DISTRIBUTION':
            raise CheckError('UNAPPROVED_CERTIFICATE_QUERY')
        url = 'https://api.appstoreconnect.apple.com' + route
        url += '?' + urllib.parse.urlencode(query)
        request = urllib.request.Request(url, method='GET', headers={
            'Authorization': 'Bearer ' + self.token, 'Accept': 'application/json',
            'User-Agent': 'AtodeYaruBox-ReadOnly-Signing-Preflight'})
        try:
            with self.opener.open(request, timeout=20) as response:
                raw = response.read(LIMIT_BYTES + 1)
            if len(raw) > LIMIT_BYTES:
                raise CheckError('RESPONSE_LIMIT_EXCEEDED')
            data = json.loads(raw)
        except urllib.error.HTTPError as error:
            raise CheckError('APPLE_HTTP_' + str(int(error.code))) from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise CheckError('APPLE_CONNECTION_FAILED') from None
        except (ValueError, UnicodeError):
            raise CheckError('APPLE_RESPONSE_INVALID') from None
        return data


def rows(response):
    if (not isinstance(response, dict) or not isinstance(response.get('data'), list)
            or any(not isinstance(row, dict) or not isinstance(row.get('attributes'), dict)
                   for row in response['data'])):
        raise CheckError('APPLE_RESPONSE_INVALID')
    if (response.get('links') or {}).get('next'):
        # Do not undercount certificate limits or follow arbitrary next URLs.
        raise CheckError('PAGINATED_RESPONSE_REQUIRES_REVIEW')
    return response['data']


def collect(getter):
    bundles = {}
    for identifier in IDENTIFIERS:
        entries = rows(getter('/v1/bundleIds', {'filter[identifier]': identifier,
            'fields[bundleIds]': 'identifier,platform', 'limit': 200}))
        if len(entries) > 1 or any(entry['attributes'].get('identifier') != identifier
                                   for entry in entries):
            raise CheckError('BUNDLE_IDENTIFIER_AMBIGUOUS')
        bundles[identifier] = 'EXISTS' if entries else 'NOT_REGISTERED'
    certificates = rows(getter('/v1/certificates', {
        'filter[certificateType]': 'DISTRIBUTION,IOS_DISTRIBUTION',
        'fields[certificates]': 'certificateType,expirationDate', 'limit': 200}))
    if any(entry['attributes'].get('certificateType') not in {'DISTRIBUTION', 'IOS_DISTRIBUTION'}
           for entry in certificates):
        raise CheckError('CERTIFICATE_RESPONSE_INVALID')
    return {'status': 'APPLE_READ_AUTHENTICATED', 'bundle_identifiers': bundles,
            'distribution_certificates_returned': len(certificates),
            'certificate_private_key_available_verified': False,
            'team_identifier_verified': False, 'app_group_membership_verified': False,
            'all_three_profiles_verified': False, 'signed_build_ready': False,
            'apple_resources_modified': False, 'binary_uploaded': False,
            'new_payment_enabled': False}


def main():
    report = {'status': 'NOT_RUN', 'authentication_verified': False,
              'signed_build_ready': False, 'apple_resources_modified': False,
              'binary_uploaded': False, 'new_payment_enabled': False,
              'checked_at': datetime.now(timezone.utc).isoformat()}
    target = ROOT / 'artifacts/apple-signing-preflight.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    def record():
        temporary = target.with_suffix('.json.tmp')
        temporary.write_text(json.dumps(report, indent=2), encoding='utf-8')
        temporary.replace(target)
    # Invalidate a previous result before any authentication/network work.
    record()
    code = 1
    try:
        token = token_from_environment(os.environ)
        report.update(collect(AppleReader(token).get))
        report['authentication_verified'] = True
        code = 0
    except CheckError as error:
        report.update(status='NOT_VERIFIED', diagnostic=str(error))
        if getattr(error, 'key_kind', None) in ('PEM', 'ESCAPED_PEM', 'BASE64_PEM', 'FILE_REFERENCE'):
            report['private_key_input_format'] = error.key_kind
        if getattr(error, 'signing_error_kind', None) in ('VALUE_ERROR', 'INVALID_KEY', 'UNSUPPORTED_ALGORITHM', 'IMPORT_ERROR', 'NOT_IMPLEMENTED', 'UNKNOWN'):
            report['signing_error_kind'] = error.signing_error_kind
    except Exception:
        report.update(status='NOT_VERIFIED', diagnostic='UNEXPECTED_PREFLIGHT_FAILURE')
    record()
    print(json.dumps(report))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
