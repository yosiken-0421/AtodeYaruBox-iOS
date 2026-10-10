"""Read capabilities/profiles for the three exact task IDs. Never changes Apple."""
import base64
from datetime import datetime, timezone
import json
from pathlib import Path
import plistlib
import re
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request

from tools.apple_signing_preflight import IDENTIFIERS, CheckError, NoRedirect, exact_bundle_rows, rows
from tools.apple_signing_resources import Client, resource_token

GROUP = 'group.jp.atodeyarubox.app'
ERROR_CODES = {'PARAMETER_ERROR.INVALID', 'PARAMETER_ERROR.UNKNOWN', 'PARAMETER_ERROR.REQUIRED',
               'ENTITY_ERROR.ATTRIBUTE.INVALID', 'FORBIDDEN_ERROR', 'NOT_FOUND', 'STATE_ERROR', 'UNKNOWN'}
PARAMETERS = {'fields[bundleIdCapabilities]', 'fields[profiles]', 'fields[bundleIds]',
              'filter[identifier]', 'limit', 'UNKNOWN'}


class InventoryError(CheckError):
    def __init__(self, diagnostic, relationship, code='UNKNOWN', parameter='UNKNOWN'):
        super().__init__(diagnostic)
        self.details = dict(relationship=relationship,
            apple_error_code=code if isinstance(code, str) and code in ERROR_CODES else 'UNKNOWN',
            parameter=parameter if isinstance(parameter, str) and parameter in PARAMETERS else 'UNKNOWN')


def related_error(error, relationship):
    # Never expose Apple's messages, IDs, profile contents or request headers.
    code, parameter = 'UNKNOWN', 'UNKNOWN'
    try:
        raw = error.read(16 * 1024 + 1)
        if len(raw) <= 16 * 1024:
            errors = json.loads(raw).get('errors')
            if isinstance(errors, list) and errors and isinstance(errors[0], dict):
                code = errors[0].get('code')
                source = errors[0].get('source')
                parameter = source.get('parameter') if isinstance(source, dict) else 'UNKNOWN'
    except Exception:
        pass
    return InventoryError('RESOURCE_HTTP_' + str(int(error.code)), relationship, code, parameter)


class RelatedReader:
    def __init__(self, token, identifiers, opener=None):
        if (not isinstance(identifiers, dict) or set(identifiers) != set(IDENTIFIERS)
                or any(not isinstance(v, str) or not re.fullmatch(r'[A-Za-z0-9-]{6,64}', v) for v in identifiers.values())
                or len(set(identifiers.values())) != 3):
            raise CheckError('INVENTORY_IDENTIFIER_MAP_INVALID')
        self.token, self.identifiers = token, identifiers
        self.opener = opener or urllib.request.build_opener(NoRedirect())

    def get(self, identifier, relationship):
        if identifier not in self.identifiers or relationship not in ('bundleIdCapabilities', 'profiles'):
            raise CheckError('INVENTORY_ROUTE_REFUSED')
        query = ({'fields[bundleIdCapabilities]': 'capabilityType,settings'}
                 if relationship == 'bundleIdCapabilities' else
                 {'fields[profiles]': 'profileType,profileState,profileContent,expirationDate', 'limit': 200})
        try:
            return self._read(identifier, relationship, query)
        except InventoryError as error:
            if str(error) != 'RESOURCE_HTTP_400':
                raise
            # Sparse fields are optional in Apple's documented API. A single
            # GET without them handles service/schema drift without changing data.
            return self._read(identifier, relationship, {})

    def _read(self, identifier, relationship, query):
        url = ('https://api.appstoreconnect.apple.com/v1/bundleIds/' + self.identifiers[identifier]
            + '/' + relationship + ('?' + urllib.parse.urlencode(query) if query else ''))
        request = urllib.request.Request(url, method='GET', headers={'Authorization': 'Bearer ' + self.token})
        try:
            with self.opener.open(request, timeout=20) as response:
                raw = response.read(1024 * 1024 + 1)
            if len(raw) > 1024 * 1024:
                raise CheckError('INVENTORY_RESPONSE_LIMIT')
            return rows(json.loads(raw))
        except urllib.error.HTTPError as error:
            raise related_error(error, relationship) from None
        except (urllib.error.URLError, OSError, TimeoutError, ValueError):
            raise CheckError('INVENTORY_READ_UNAVAILABLE') from None


def decode_profile(content):
    try:
        if not isinstance(content, str) or len(content) > 256 * 1024:
            raise ValueError()
        raw = base64.b64decode(content, validate=True)
        with tempfile.TemporaryDirectory(prefix='atode-profile-read-') as folder:
            path = Path(folder) / 'profile.mobileprovision'
            path.write_bytes(raw)
            path.chmod(0o600)
            process = subprocess.run(['security', 'cms', '-D', '-i', str(path)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
            if process.returncode or len(process.stdout) > 512 * 1024:
                raise ValueError()
            return plistlib.loads(process.stdout)
    except Exception:
        raise CheckError('INVENTORY_PROFILE_DECODE_UNVERIFIED') from None


def summarize(getter, decoder=decode_profile):
    summary = {}
    for identifier in IDENTIFIERS:
        capabilities = getter(identifier, 'bundleIdCapabilities')
        profiles = getter(identifier, 'profiles')
        enabled = any(e['attributes'].get('capabilityType') == 'APP_GROUPS' for e in capabilities)
        matched, distribution = 0, 0
        for entry in profiles:
            attributes = entry['attributes']
            if attributes.get('profileState') != 'ACTIVE':
                continue
            profile = decoder(attributes.get('profileContent'))
            entitlement = profile.get('Entitlements', {})
            expiry = profile.get('ExpirationDate')
            if (not isinstance(entitlement, dict) or not isinstance(expiry, datetime)
                    or expiry.replace(tzinfo=timezone.utc) <= datetime.now(timezone.utc)
                    or entitlement.get('application-identifier', '').split('.', 1)[-1] != identifier):
                continue
            groups = entitlement.get('com.apple.security.application-groups')
            if groups == [GROUP]:
                matched += 1
                if (attributes.get('profileType') == 'IOS_APP_STORE' and entitlement.get('get-task-allow') is False
                        and 'ProvisionedDevices' not in profile and profile.get('ProvisionsAllDevices') is not True):
                    distribution += 1
        summary[identifier] = dict(app_groups_capability_enabled=enabled, profiles_returned=len(profiles),
            active_profiles_with_exact_group=matched, app_store_profiles_with_exact_group=distribution)
    return summary


def inspect(environment):
    token = resource_token(environment)
    client = Client(token, '')
    identifiers = {}
    for identifier in IDENTIFIERS:
        try:
            response = client.request('/v1/bundleIds', query={'filter[identifier]': identifier,
                'fields[bundleIds]': 'identifier,platform,seedId', 'limit': 200})
        except CheckError as error:
            if str(error) != 'RESOURCE_HTTP_400':
                raise InventoryError(str(error), 'bundleIds') from None
            try:
                response = client.request('/v1/bundleIds', query={'filter[identifier]': identifier, 'limit': 200})
            except CheckError as retry_error:
                raise InventoryError(str(retry_error), 'bundleIds') from None
        exact = exact_bundle_rows(rows(response), identifier)
        if len(exact) != 1:
            raise CheckError('INVENTORY_TASK_IDENTIFIER_MISSING')
        identifiers[identifier] = exact[0].get('id')
    reader = RelatedReader(token, identifiers)
    return summarize(reader.get)
