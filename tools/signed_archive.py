"""Prepare and verify a private signed package. Never uploads it to Apple."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import plistlib
import re
import secrets
import subprocess
import sys
import tempfile
import zipfile

from tools.apple_signing_preflight import CheckError, IDENTIFIERS, normalize_private_key
from tools.apple_signing_resources import prepare
from tools import generate_project

ROOT = Path(__file__).resolve().parents[1]
GROUP = 'group.jp.atodeyarubox.app'
TARGETS = ('AtodeYaruBox', 'BoxShare', 'BoxWidgets')
REPORT = ROOT / 'artifacts/signed-package-result.json'


def identity_container(key, certificate, password):
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.serialization import PrivateFormat, pkcs12
    # Use the documented macOS compatibility format after CI import failed.
    # The file exists
    # only in a mode-0700 ephemeral CI folder and is never an artifact or backup.
    # https://cryptography.io/en/50.0.2/hazmat/primitives/asymmetric/serialization/
    encryption = (PrivateFormat.PKCS12.encryption_builder().kdf_rounds(50000)
        .key_cert_algorithm(pkcs12.PBES.PBESv1SHA1And3KeyTripleDESCBC)
        .hmac_hash(hashes.SHA1()).build(password.encode('ascii')))
    return pkcs12.serialize_key_and_certificates(b'AtodeYaruBox', key, certificate, None, encryption)


def manual_settings(team, materials, certificate_sha1):
    if not isinstance(team, str) or not re.fullmatch(r'[A-Z0-9]{10}', team):
        raise CheckError('TEAM_IDENTIFIER_INVALID')
    if (not isinstance(materials, dict) or set(materials) != set(IDENTIFIERS)
            or not isinstance(certificate_sha1, str) or not re.fullmatch(r'[0-9a-f]{40}', certificate_sha1)):
        raise CheckError('MANUAL_SIGNING_MATERIAL_UNVERIFIED')
    result = {}
    uuids = set()
    for identifier in IDENTIFIERS:
        value = materials[identifier].get('uuid')
        if (not isinstance(value, str) or not re.fullmatch(r'[0-9A-Fa-f]{8}(?:-[0-9A-Fa-f]{4}){3}-[0-9A-Fa-f]{12}', value)
                or value.lower() in uuids):
            raise CheckError('MANUAL_SIGNING_MATERIAL_UNVERIFIED')
        uuids.add(value.lower())
        result[identifier] = dict(DEVELOPMENT_TEAM=team, CODE_SIGN_STYLE='Manual',
            CODE_SIGN_IDENTITY=certificate_sha1, PROVISIONING_PROFILE_SPECIFIER=value,
            CODE_SIGNING_ALLOWED='YES', CODE_SIGNING_REQUIRED='YES')
    return result


def export_options(team, materials=None, certificate_sha1=None):
    if not isinstance(team, str) or not re.fullmatch(r'[A-Z0-9]{10}', team):
        raise CheckError('TEAM_IDENTIFIER_INVALID')
    options = dict(method='app-store-connect', destination='export', signingStyle='automatic',
                teamID=team, manageAppVersionAndBuildNumber=False, uploadSymbols=False,
                testFlightInternalTestingOnly=True)
    if materials is not None:
        settings = manual_settings(team, materials, certificate_sha1)
        options.update(signingStyle='manual', signingCertificate=certificate_sha1,
            provisioningProfiles={identifier: settings[identifier]['PROVISIONING_PROFILE_SPECIFIER'] for identifier in IDENTIFIERS})
    return options


def install_profiles(materials):
    # Xcode 16+ uses this CI user's private directory. Never overwrite files.
    folder = Path.home() / 'Library/Developer/Xcode/UserData/Provisioning Profiles'
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    for identifier in IDENTIFIERS:
        material = materials[identifier]
        path = folder / (material['uuid'] + '.mobileprovision')
        if path.exists():
            if path.read_bytes() != material['content']:
                raise CheckError('PROFILE_INSTALL_COLLISION')
        else:
            with path.open('xb') as stream:
                stream.write(material['content'])
            path.chmod(0o600)


def apply_manual_project(objects, team, materials, certificate_sha1, configuration):
    # Resolve only the one verified xcconfig macro used by this generator.
    identifiers = re.findall(r'^APP_BUNDLE_ID\s*=\s*(\S+)\s*$', configuration, re.MULTILINE)
    if identifiers != [IDENTIFIERS[0]]:
        raise CheckError('MANUAL_SIGNING_TARGET_MISMATCH')
    settings = manual_settings(team, materials, certificate_sha1)
    for name, identifier in zip(TARGETS, IDENTIFIERS):
        for configuration_name in ('Debug', 'Release'):
            target_config = objects[generate_project.uid('config:' + name + ':' + configuration_name)]
            value = target_config['buildSettings'].get('PRODUCT_BUNDLE_IDENTIFIER')
            if not isinstance(value, str) or value.replace('$(APP_BUNDLE_ID)', IDENTIFIERS[0]) != identifier:
                raise CheckError('MANUAL_SIGNING_TARGET_MISMATCH')
            target_config['buildSettings'].update(settings[identifier], PRODUCT_BUNDLE_IDENTIFIER=identifier)


def validate_profile(profile, identifier, team, distribution=False):
    entitlements = profile.get('Entitlements', {})
    if (profile.get('TeamIdentifier') != [team]
            or entitlements.get('com.apple.developer.team-identifier') != team
            or entitlements.get('application-identifier', '').split('.', 1)[-1] != identifier
            or entitlements.get('com.apple.security.application-groups') != [GROUP]):
        raise CheckError('PROFILE_ID_TEAM_OR_GROUP_MISMATCH')
    if distribution and (entitlements.get('get-task-allow') is not False
                         or 'ProvisionedDevices' in profile or profile.get('ProvisionsAllDevices') is True):
        raise CheckError('PROFILE_NOT_APP_STORE_DISTRIBUTION')
    expiry = profile.get('ExpirationDate')
    if not isinstance(expiry, datetime) or expiry.replace(tzinfo=timezone.utc) <= datetime.now(timezone.utc):
        raise CheckError('PROFILE_EXPIRED_OR_UNVERIFIED')


def classify_build_failure(raw):
    text = raw.decode('utf-8', errors='replace').lower()
    if 'app group' in text and ('not registered' in text or 'cannot be registered' in text):
        return 'APP_GROUP_REGISTRATION_REQUIRED'
    if 'com.apple.security.application-groups' in text:
        return 'PROFILE_APP_GROUP_SETUP_REQUIRED'
    if 'no devices' in text or 'no registered devices' in text:
        return 'DEVELOPMENT_PROFILE_DEVICE_REQUIRED'
    if 'no accounts' in text or 'add a new account' in text:
        return 'APPLE_ACCOUNT_REQUIRED'
    if 'conflicting provisioning settings' in text:
        return 'PROVISIONING_SETTINGS_CONFLICT'
    if 'permission' in text or 'forbidden' in text:
        return 'SIGNING_PERMISSION_REQUIRED'
    return 'SIGNED_BUILD_FAILED'


def classify_command_failure(stage, raw):
    if stage in ('archive', 'export'):
        return classify_build_failure(raw)
    text = raw.decode('utf-8', errors='replace').lower()
    if stage == 'keychain_import' and ('mac verification failed' in text or 'pkcs12' in text and 'decode' in text):
        return 'PKCS12_COMPATIBILITY_REQUIRED'
    return 'COMMAND_FAILED'


def verify_product(app, team, distribution, runner, certificate_der=None):
    bundles = (app, app / 'PlugIns/BoxShare.appex', app / 'PlugIns/BoxWidgets.appex')
    for bundle, identifier in zip(bundles, IDENTIFIERS):
        try:
            info = plistlib.loads((bundle / 'Info.plist').read_bytes())
        except Exception:
            raise CheckError('SIGNED_PRODUCT_METADATA_MISSING') from None
        if info.get('CFBundleIdentifier') != identifier or not (bundle / 'PrivacyInfo.xcprivacy').is_file():
            raise CheckError('SIGNED_PRODUCT_ID_OR_PRIVACY_MISMATCH')
        runner(['codesign', '--verify', '--strict', str(bundle)], stage='signature_verify')
        data = runner(['security', 'cms', '-D', '-i', str(bundle / 'embedded.mobileprovision')], stage='profile_decode')
        try:
            profile = plistlib.loads(data)
        except Exception:
            raise CheckError('PROFILE_CONTENT_INVALID') from None
        validate_profile(profile, identifier, team, distribution)
        if certificate_der is not None and profile.get('DeveloperCertificates') != [certificate_der]:
            raise CheckError('PROFILE_CERTIFICATE_MISMATCH')
        signed_entitlements = runner(['codesign', '-d', '--entitlements', ':-', str(bundle)], stage='entitlements_read')
        try:
            signed = plistlib.loads(signed_entitlements)
        except Exception:
            raise CheckError('SIGNED_ENTITLEMENTS_INVALID') from None
        if (signed.get('com.apple.security.application-groups') != [GROUP]
                or signed.get('com.apple.developer.team-identifier') != team
                or signed.get('application-identifier') != profile['Entitlements']['application-identifier']
                or distribution and signed.get('get-task-allow') is not False):
            raise CheckError('SIGNED_ENTITLEMENTS_PROFILE_MISMATCH')
    runner(['codesign', '--verify', '--deep', '--strict', str(app)], stage='signature_verify')


def main():
    REPORT.parent.mkdir(exist_ok=True, parents=True)
    result = dict(status='NOT_RUN', signed_archive_verified=False, signed_ipa_verified=False,
                  apple_resources_modified=False, binary_uploaded=False, billing_modified=False,
                  private_key_disclosed=False, native_tests_repeated=False, stage='preflight',
                  verified_native_source='300dc7f7143c3c9e6fc0615effe70bd10efb6950')
    def record():
        tmp = REPORT.with_suffix('.json.tmp')
        tmp.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
        tmp.replace(REPORT)
    record()
    if platform.system() != 'Darwin':
        result.update(status='NOT_VERIFIED', diagnostic='MACOS_REQUIRED')
        record()
        return 1
    if sys.argv[1:] == ['--inspect-provisioning']:
        from tools.apple_provisioning_inventory import inspect, InventoryError
        result['stage'] = 'inventory'
        try:
            result.update(status='SIGNING_INVENTORY_READ', provisioning_inventory=inspect(os.environ))
        except InventoryError as error:
            result.update(status='NOT_VERIFIED', diagnostic=str(error), inventory_failure=error.details)
        except CheckError as error:
            result.update(status='NOT_VERIFIED', diagnostic=str(error))
        except Exception:
            result.update(status='NOT_VERIFIED', diagnostic='INVENTORY_READ_UNAVAILABLE')
        record()
        print(json.dumps(result))
        return 0 if result['status'] == 'SIGNING_INVENTORY_READ' else 1
    if sys.argv[1:] == ['--prepare-distribution-profiles']:
        from tools.apple_distribution_profiles import prepare_distribution
        result.update(stage='profile_prepare', profiles_created_count=0)
        def profile_checkpoint(stage):
            result.update(stage='profile_prepare', apple_resources_modified=True)
            if stage == 'PROFILE_CREATED':
                result['profiles_created_count'] += 1
            record()
        try:
            result.update(prepare_distribution(os.environ, profile_checkpoint))
            result['status'] = 'DISTRIBUTION_PROFILES_VERIFIED'
        except CheckError as error:
            result.update(status='NOT_VERIFIED', diagnostic=str(error))
        except Exception:
            result.update(status='NOT_VERIFIED', diagnostic='PROFILE_PREPARATION_UNAVAILABLE')
        record()
        print(json.dumps(result))
        return 0 if result['status'] == 'DISTRIBUTION_PROFILES_VERIFIED' else 1
    manual = sys.argv[1:] == ['--manual-distribution-refresh']
    if sys.argv[1:] and not manual:
        result.update(status='NOT_VERIFIED', diagnostic='UNAPPROVED_SIGNING_MODE')
        record()
        return 1
    def checkpoint(stage):
        result.update(stage=stage, apple_resources_modified=True)
        record()
    def run(args, stage, timeout=600):
        result['stage'] = stage
        record()
        try:
            p = subprocess.run(args, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
        except subprocess.TimeoutExpired:
            raise CheckError('COMMAND_TIMEOUT') from None
        except OSError:
            raise CheckError('COMMAND_UNAVAILABLE') from None
        if stage in ('archive', 'export'):
            result['compile_errors'] = len(re.findall(rb':\d+:\d+:\s+error:', p.stdout + p.stderr))
            result['compiler_warnings'] = len(re.findall(rb':\d+:\d+:\s+warning:', p.stdout + p.stderr))
        if p.returncode:
            raise CheckError(classify_command_failure(stage, p.stdout + p.stderr))
        return p.stdout
    try:
        with tempfile.TemporaryDirectory(prefix='atode-signing-') as directory:
            folder = Path(directory)
            materials, certificate_der, certificate_sha1 = None, None, None
            if manual:
                from tools.apple_distribution_profiles import prepare_material
                from cryptography.hazmat.primitives.serialization import Encoding
                result.update(stage='profile_prepare', profiles_created_count=0)
                def profile_checkpoint(stage):
                    result.update(stage='profile_prepare', apple_resources_modified=True)
                    if stage == 'PROFILE_CREATED':
                        result['profiles_created_count'] += 1
                    record()
                key, certificate, team, metadata, materials = prepare_material(os.environ, profile_checkpoint, refreshed=True)
                certificate_der = certificate.public_bytes(Encoding.DER)
                certificate_sha1 = hashlib.sha1(certificate_der).hexdigest()
                result.update(distribution_profiles_verified=True, verified_distribution_profiles=3)
                result['stage'] = 'profile_install'
                record()
                manual_settings(team, materials, certificate_sha1)
                install_profiles(materials)
            else:
                key, certificate, team, metadata = prepare(os.environ, checkpoint)
            result.update(metadata)
            record()
            identity = folder / 'identity.p12'
            identity_password = secrets.token_urlsafe(32)
            identity.write_bytes(identity_container(key, certificate, identity_password))
            identity.chmod(0o600)
            authentication = []
            if not manual:
                api_key = folder / 'AuthKey.p8'
                api_key.write_text(normalize_private_key(os.environ.get('APP_STORE_CONNECT_PRIVATE_KEY'))[0], encoding='utf-8')
                api_key.chmod(0o600)
                authentication = ['-allowProvisioningUpdates', '-authenticationKeyPath', str(api_key),
                    '-authenticationKeyID', os.environ['APP_STORE_CONNECT_KEY_IDENTIFIER'],
                    '-authenticationKeyIssuerID', os.environ['APP_STORE_CONNECT_ISSUER_ID']]
            keychain = folder / 'signing.keychain-db'
            password = secrets.token_urlsafe(32)
            run(['security', 'create-keychain', '-p', password, str(keychain)], 'keychain_create')
            run(['security', 'set-keychain-settings', '-lut', '21600', str(keychain)], 'keychain_settings')
            run(['security', 'unlock-keychain', '-p', password, str(keychain)], 'keychain_unlock')
            previous = run(['security', 'list-keychains', '-d', 'user'], 'keychain_read').decode()
            previous_paths = re.findall(r'"([^"\n]+)"', previous)
            run(['security', 'list-keychains', '-d', 'user', '-s', str(keychain)] + previous_paths, 'keychain_search')
            run(['security', 'import', str(identity), '-k', str(keychain), '-f', 'pkcs12', '-P', identity_password,
                 '-T', '/usr/bin/codesign', '-T', '/usr/bin/security'], 'keychain_import')
            run(['security', 'set-key-partition-list', '-S', 'apple-tool:,apple:,codesign:', '-s', '-k', password, str(keychain)], 'keychain_partition')
            generate_project.main()
            # Add signing metadata only to the generated CI project; the verified
            # Swift sources and generator stay identical to the accepted native run.
            project = generate_project.OBJECTS[generate_project.uid('project')]
            project['attributes']['TargetAttributes'] = {
                generate_project.uid('target:' + name): {'DevelopmentTeam': team,
                    'ProvisioningStyle': 'Manual' if manual else 'Automatic',
                    'SystemCapabilities': {'com.apple.ApplicationGroups.iOS': {'enabled': 1}}}
                for name in TARGETS}
            if manual:
                apply_manual_project(generate_project.OBJECTS, team, materials, certificate_sha1,
                    (ROOT / 'Config/App.xcconfig').read_text(encoding='utf-8'))
            document = dict(archiveVersion=1, classes={}, objectVersion=56,
                objects=dict(sorted(generate_project.OBJECTS.items())), rootObject=generate_project.uid('project'))
            (generate_project.PROJECT / 'project.pbxproj').write_text('// !$*UTF8*$!\n' + generate_project.encode(document) + '\n', encoding='utf-8')
            archive = folder / 'AtodeYaruBox.xcarchive'
            if manual:
                result['stage'] = 'MANUAL_SIGNING_PREPARED'
                record()
            else:
                checkpoint('AUTOMATIC_SIGNING_RESERVED')
            overrides = (['CODE_SIGNING_ALLOWED=YES', 'CODE_SIGNING_REQUIRED=YES'] if manual else
                ['DEVELOPMENT_TEAM=' + team, 'CODE_SIGN_STYLE=Automatic', 'CODE_SIGNING_ALLOWED=YES',
                 'CODE_SIGNING_REQUIRED=YES', 'REGISTER_APP_GROUPS=YES'])
            run(['xcodebuild', '-project', 'AtodeYaruBox.xcodeproj', '-scheme', 'AtodeYaruBox',
                 '-configuration', 'Release', '-destination', 'generic/platform=iOS', '-archivePath', str(archive),
                 '-derivedDataPath', str(folder / 'DerivedData')] + authentication +
                overrides + ['archive'], 'archive', timeout=720)
            verify_product(archive / 'Products/Applications/AtodeYaruBox.app', team, manual, run, certificate_der)
            result['signed_archive_verified'] = True
            options = folder / 'ExportOptions.plist'
            options.write_bytes(plistlib.dumps(export_options(team, materials, certificate_sha1)))
            exported = folder / 'exported'
            run(['xcodebuild', '-exportArchive', '-archivePath', str(archive), '-exportOptionsPlist', str(options),
                 '-exportPath', str(exported)] + authentication, 'export', timeout=360)
            packages = list(exported.glob('*.ipa'))
            if len(packages) != 1:
                raise CheckError('SIGNED_IPA_NOT_UNIQUE')
            unpacked = folder / 'unpacked'
            unpacked.mkdir()
            with zipfile.ZipFile(packages[0]) as package:
                if sum(i.file_size for i in package.infolist()) > 500 * 1024 * 1024:
                    raise CheckError('SIGNED_IPA_SIZE_REFUSED')
                for member in package.infolist():
                    if not (unpacked / member.filename).resolve().is_relative_to(unpacked.resolve()):
                        raise CheckError('SIGNED_IPA_PATH_REFUSED')
                package.extractall(unpacked)
            verify_product(unpacked / 'Payload/AtodeYaruBox.app', team, True, run, certificate_der)
            payload = packages[0].read_bytes()
            (ROOT / 'artifacts/AtodeYaruBox.ipa').write_bytes(payload)
            result.update(status='SIGNED_PACKAGE_VERIFIED', signed_ipa_verified=True,
                          ipa_sha256=hashlib.sha256(payload).hexdigest(), ipa_size_bytes=len(payload), stage='complete')
    except CheckError as error:
        result.update(status='NOT_VERIFIED', diagnostic=str(error))
    except Exception:
        result.update(status='NOT_VERIFIED', diagnostic='UNEXPECTED_SIGNED_PACKAGE_FAILURE')
    record()
    print(json.dumps(result))
    return 0 if result['status'] == 'SIGNED_PACKAGE_VERIFIED' else 1


if __name__ == '__main__':
    raise SystemExit(main())
