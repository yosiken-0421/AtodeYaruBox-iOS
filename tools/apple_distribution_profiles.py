"""Create only task App Store profiles using the existing matching certificate."""
import base64
import json
import re
import urllib.error
import urllib.request

from tools.apple_signing_preflight import CheckError, IDENTIFIERS, NoRedirect, rows, exact_bundle_rows
from tools.apple_signing_resources import Client, certificate_query, prepare, resource_token
from tools.apple_provisioning_inventory import RelatedReader, decode_profile

NAMES = dict(zip(IDENTIFIERS, ('AtodeYaruBox CI App Store', 'AtodeYaruBox Share CI App Store', 'AtodeYaruBox Widgets CI App Store')))


def resource_id(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9-]{6,64}', value):
        raise CheckError('PROFILE_RESOURCE_ID_UNVERIFIED')
    return value


def body(identifier, bundle, certificate):
    if identifier not in IDENTIFIERS:
        raise CheckError('PROFILE_ROUTE_REFUSED')
    return {'data': {'type': 'profiles', 'attributes': {'name': NAMES[identifier], 'profileType': 'IOS_APP_STORE'},
        'relationships': {'bundleId': {'data': {'type': 'bundleIds', 'id': resource_id(bundle)}},
            'certificates': {'data': [{'type': 'certificates', 'id': resource_id(certificate)}]}}}}


class Creator:
    def __init__(self, token, identifiers, certificate, checkpoint, opener=None):
        RelatedReader(token, identifiers)  # Validate exact task mapping and IDs.
        self.token, self.identifiers, self.certificate = token, identifiers, resource_id(certificate)
        self.checkpoint, self.attempted = checkpoint, set()
        self.opener = opener or urllib.request.build_opener(NoRedirect())

    def create(self, identifier):
        if identifier not in self.identifiers or identifier in self.attempted:
            raise CheckError('PROFILE_ROUTE_OR_REPLAY_REFUSED')
        payload = body(identifier, self.identifiers[identifier], self.certificate)
        self.attempted.add(identifier)
        self.checkpoint('PROFILE_POST_RESERVED')
        request = urllib.request.Request('https://api.appstoreconnect.apple.com/v1/profiles', method='POST',
            data=json.dumps(payload).encode(), headers={'Authorization': 'Bearer ' + self.token, 'Content-Type': 'application/json'})
        try:
            with self.opener.open(request, timeout=20) as response:
                raw = response.read(1024 * 1024 + 1)
            if len(raw) > 1024 * 1024:
                raise CheckError('PROFILE_RESPONSE_LIMIT')
            value = json.loads(raw).get('data')
            if not isinstance(value, dict) or value.get('type') != 'profiles' or not isinstance(value.get('attributes'), dict):
                raise CheckError('PROFILE_CREATION_OUTCOME_UNVERIFIED')
            self.checkpoint('PROFILE_CREATED')
            return value
        except urllib.error.HTTPError as error:
            raise CheckError('RESOURCE_HTTP_' + str(int(error.code))) from None
        except (urllib.error.URLError, OSError, TimeoutError, ValueError):
            raise CheckError('PROFILE_REQUEST_OUTCOME_UNAVAILABLE') from None


def verify_profile(entry, identifier, certificate_der, team, decoder=decode_profile):
    from tools.signed_archive import validate_profile, GROUP
    attributes = entry.get('attributes', {})
    if attributes.get('profileType') != 'IOS_APP_STORE' or attributes.get('profileState') != 'ACTIVE':
        raise CheckError('PROFILE_NOT_APP_STORE_DISTRIBUTION')
    profile = decoder(attributes.get('profileContent'))
    if profile.get('Entitlements', {}).get('com.apple.security.application-groups') != [GROUP]:
        raise CheckError('APP_GROUP_PROFILE_ASSIGNMENT_REQUIRED')
    validate_profile(profile, identifier, team, distribution=True)
    if profile.get('DeveloperCertificates') != [certificate_der]:
        raise CheckError('PROFILE_CERTIFICATE_MISMATCH')
    return profile


def prepare_distribution(environment, checkpoint):
    from cryptography.hazmat.primitives.serialization import Encoding
    _, certificate, team, _ = prepare(environment, allow_create=False)
    certificate_der = certificate.public_bytes(Encoding.DER)
    token = resource_token(environment)
    client = Client(token, '')
    identifiers = {}
    for identifier in IDENTIFIERS:
        entries = exact_bundle_rows(rows(client.request('/v1/bundleIds', query={'filter[identifier]': identifier,
            'fields[bundleIds]': 'identifier,platform,seedId', 'limit': 200})), identifier)
        if len(entries) != 1:
            raise CheckError('EXISTING_SIGNING_RESOURCES_REQUIRED')
        identifiers[identifier] = resource_id(entries[0].get('id'))
    matches = [e for e in rows(client.request('/v1/certificates', query=certificate_query()))
        if e['attributes'].get('certificateContent') == base64.b64encode(certificate_der).decode('ascii')]
    if len(matches) != 1:
        raise CheckError('MATCHING_CERTIFICATE_AMBIGUOUS')
    creator = Creator(token, identifiers, matches[0].get('id'), checkpoint)
    reader = RelatedReader(token, identifiers)
    verified = 0
    for identifier in IDENTIFIERS:
        existing = [e for e in reader.get(identifier, 'profiles') if e['attributes'].get('name') == NAMES[identifier]]
        if len(existing) > 1:
            raise CheckError('PROFILE_OWNED_MATCH_AMBIGUOUS')
        entry = existing[0] if existing else creator.create(identifier)
        verify_profile(entry, identifier, certificate_der, team)
        verified += 1
    return dict(distribution_profiles_verified=verified == 3, verified_distribution_profiles=verified)
