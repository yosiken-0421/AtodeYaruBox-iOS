"""GET only the main app's App Store Connect record; never creates or uploads."""
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from tools.apple_signing_preflight import CheckError, IDENTIFIERS, NoRedirect, rows, token_from_environment

QUERY = {'filter[bundleId]': IDENTIFIERS[0], 'fields[apps]': 'bundleId', 'limit': 2}
ROUTE = '/v1/apps?' + urllib.parse.urlencode(QUERY)
URL = 'https://api.appstoreconnect.apple.com' + ROUTE


def token(environment, encoder=None):
    if encoder is None:
        import jwt
        encoder = jwt.encode
    def scoped(payload, key, **options):
        return encoder({**payload, 'scope': ['GET ' + ROUTE]}, key, **options)
    return token_from_environment(environment, scoped)


def read(token_value, opener=None):
    opener = opener or urllib.request.build_opener(NoRedirect())
    request = urllib.request.Request(URL, method='GET', headers={'Authorization': 'Bearer ' + token_value})
    try:
        with opener.open(request, timeout=20) as response:
            raw = response.read(64 * 1024 + 1)
        if len(raw) > 64 * 1024:
            raise CheckError('APP_RECORD_RESPONSE_LIMIT')
        entries = rows(json.loads(raw))
        if (len(entries) > 1 or any(e.get('type') != 'apps' or e['attributes'].get('bundleId') != IDENTIFIERS[0]
                or not isinstance(e.get('id'), str) or not re.fullmatch(r'[0-9]{6,12}', e['id']) for e in entries)):
            raise CheckError('APP_RECORD_IDENTITY_UNVERIFIED')
        result = dict(app_record_read_verified=True, app_record_exists=bool(entries))
        if entries:
            result['app_record_id'] = entries[0]['id']
        return result
    except urllib.error.HTTPError as error:
        raise CheckError('APPLE_HTTP_' + str(int(error.code))) from None
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        raise CheckError('APP_RECORD_READ_UNAVAILABLE') from None


def inspect(environment):
    return read(token(environment))
