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


def export_options(team):
    if not isinstance(team, str) or not re.fullmatch(r'[A-Z0-9]{10}', team):
        raise CheckError('TEAM_IDENTIFIER_INVALID')
    return dict(method='app-store-connect', destination='export', signingStyle='automatic',
                teamID=team, manageAppVersionAndBuildNumber=False, uploadSymbols=False,
                testFlightInternalTestingOnly=True)


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


def verify_product(app, team, distribution, runner):
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
    if sys.argv[1:]:
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
            key, certificate, team, metadata = prepare(os.environ, checkpoint)
            result.update(metadata)
            record()
            identity = folder / 'identity.p12'
            identity_password = secrets.token_urlsafe(32)
            identity.write_bytes(identity_container(key, certificate, identity_password))
            identity.chmod(0o600)
            api_key = folder / 'AuthKey.p8'
            api_key.write_text(normalize_private_key(os.environ.get('APP_STORE_CONNECT_PRIVATE_KEY'))[0], encoding='utf-8')
            api_key.chmod(0o600)
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
                    'ProvisioningStyle': 'Automatic',
                    'SystemCapabilities': {'com.apple.ApplicationGroups.iOS': {'enabled': 1}}}
                for name in TARGETS}
            document = dict(archiveVersion=1, classes={}, objectVersion=56,
                objects=dict(sorted(generate_project.OBJECTS.items())), rootObject=generate_project.uid('project'))
            (generate_project.PROJECT / 'project.pbxproj').write_text('// !$*UTF8*$!\n' + generate_project.encode(document) + '\n', encoding='utf-8')
            authentication = ['-allowProvisioningUpdates', '-authenticationKeyPath', str(api_key),
                '-authenticationKeyID', os.environ['APP_STORE_CONNECT_KEY_IDENTIFIER'],
                '-authenticationKeyIssuerID', os.environ['APP_STORE_CONNECT_ISSUER_ID']]
            archive = folder / 'AtodeYaruBox.xcarchive'
            checkpoint('AUTOMATIC_SIGNING_RESERVED')
            run(['xcodebuild', '-project', 'AtodeYaruBox.xcodeproj', '-scheme', 'AtodeYaruBox',
                 '-configuration', 'Release', '-destination', 'generic/platform=iOS', '-archivePath', str(archive),
                 '-derivedDataPath', str(folder / 'DerivedData')] + authentication +
                ['DEVELOPMENT_TEAM=' + team, 'CODE_SIGN_STYLE=Automatic', 'CODE_SIGNING_ALLOWED=YES',
                 'CODE_SIGNING_REQUIRED=YES', 'REGISTER_APP_GROUPS=YES', 'archive'], 'archive', timeout=720)
            verify_product(archive / 'Products/Applications/AtodeYaruBox.app', team, False, run)
            result['signed_archive_verified'] = True
            options = folder / 'ExportOptions.plist'
            options.write_bytes(plistlib.dumps(export_options(team)))
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
            verify_product(unpacked / 'Payload/AtodeYaruBox.app', team, True, run)
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
