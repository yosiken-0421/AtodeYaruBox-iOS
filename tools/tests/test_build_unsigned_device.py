"""Host regressions with synthetic products; these never execute Xcode."""
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import plistlib
import tempfile
import unittest
from unittest.mock import patch

from tools import build_unsigned_device as module


class UnsignedDeviceBuildTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix='atode-device-host-')
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.artifacts = self.root / 'artifacts'
        self.artifacts.mkdir()
        self.sha = 'a' * 40
        self.commands = []
        self.debug = self.artifacts / 'ios-build-result.json'
        self.debug.write_text('{"build":"PASS","tests":"PASS"}')
        self.original_debug = self.debug.read_bytes()
        for owner, name, value in [(module,'ROOT',self.root),(module,'ARTIFACTS',self.artifacts)]:
            replacement = patch.object(owner,name,value)
            replacement.start()
            self.addCleanup(replacement.stop)

    def execute(self, arguments, name, *, build_exit=0, supported_platform='iPhoneOS', signed=False, warning=False):
        self.commands.append(arguments)
        if arguments[-1] == 'archive':
            if build_exit:
                return build_exit, 'error: synthetic native archive failure'
            archive = Path(arguments[arguments.index('-archivePath') + 1])
            app = archive / 'Products/Applications/AtodeYaruBox.app'
            for suffix, executable, identifier in [('', 'AtodeYaruBox', 'jp.atodeyarubox.app'),
                ('PlugIns/BoxShare.appex', 'BoxShare', 'jp.atodeyarubox.app.share'),
                ('PlugIns/BoxWidgets.appex', 'BoxWidgets', 'jp.atodeyarubox.app.widgets')]:
                bundle = app / suffix
                bundle.mkdir(parents=True)
                (bundle / executable).write_bytes(b'Synthetic host product, not Mach-O')
                (bundle / 'PrivacyInfo.xcprivacy').write_text('Synthetic fixture')
                (bundle / 'Info.plist').write_bytes(plistlib.dumps({'CFBundleIdentifier':identifier,
                    'CFBundleExecutable':executable,'CFBundleSupportedPlatforms':[supported_platform]}))
            return 0, '** ARCHIVE SUCCEEDED **' + ('\nShared/Fixture.swift:2:3: warning: synthetic warning' if warning else '')
        if arguments[0] == 'lipo':
            return 0, 'arm64\n'
        if arguments[0] == 'codesign':
            return (0, 'Identifier=synthetic') if signed else (1, 'fixture: code object is not signed at all')
        return 0, 'Synthetic host preflight'

    def build(self, **options):
        with patch.object(module.platform,'system',return_value='Darwin'), \
             patch.object(module.shutil,'which',return_value='/usr/bin/xcodebuild'), \
             patch.object(module.subprocess,'check_output',return_value=self.sha), \
             patch.object(module.builder,'generate'), \
             patch.object(module.builder,'execute',side_effect=lambda arguments,name: self.execute(arguments,name,**options)), \
             patch.dict(os.environ,{'GITHUB_SHA':self.sha}), redirect_stdout(io.StringIO()):
            code = module.main()
        self.assertEqual(self.debug.read_bytes(),self.original_debug)
        return code,json.loads((self.artifacts / 'unsigned-device-build.json').read_text())

    def testArchiveUsesDeviceSDKAndNeverSignsOrClaimsInstallation(self):
        code,result = self.build()
        self.assertEqual(code,0)
        self.assertEqual(result['archive'],'PASS')
        self.assertEqual(result['source_sha'],self.sha)
        self.assertFalse(result['signed'])
        self.assertFalse(result['iphone_installable'])
        self.assertFalse(result['device_execution_verified'])
        command = next(arguments for arguments in self.commands if arguments[-1] == 'archive')
        for value in ['Release','iphoneos','generic/platform=iOS','CODE_SIGNING_ALLOWED=NO','CODE_SIGNING_REQUIRED=NO']:
            self.assertIn(value,command)
        self.assertNotIn('-allowProvisioningUpdates',command)
        self.assertEqual(sum(arguments[0] == 'codesign' for arguments in self.commands),3)
        self.assertTrue(all('-d' in arguments for arguments in self.commands if arguments[0] == 'codesign'))

    def testFailureAndUnsupportedHostReplaceOldPassWhilePreservingDebugAcceptance(self):
        path = self.artifacts / 'unsigned-device-build.json'
        path.write_text('{"archive":"PASS"}')
        code,result = self.build(build_exit=65)
        self.assertEqual(code,1)
        self.assertEqual(result['archive'],'FAIL')
        self.assertEqual(result['archive_exit_code'],65)
        path.write_text('{"archive":"PASS"}')
        with patch.object(module.platform,'system',return_value='Windows'),redirect_stdout(io.StringIO()):
            code = module.main()
        self.assertEqual(code,2)
        self.assertEqual(json.loads(path.read_text())['archive'],'NOT_RUN')
        self.assertEqual(self.debug.read_bytes(),self.original_debug)

    def testSimulatorProductsAndUnexpectedSignatureCannotPassDeviceVerification(self):
        for options in [{'supported_platform':'iPhoneSimulator'},{'signed':True}]:
            with self.subTest(options=options):
                code,result = self.build(**options)
                self.assertEqual(code,1)
                self.assertEqual(result['archive'],'FAIL')
                self.assertTrue(result['errors'])

    def testZeroExitCannotHideCompilerWarnings(self):
        code,result = self.build(warning=True)
        self.assertEqual(code,1)
        self.assertEqual(result['archive'],'FAIL')
        self.assertTrue(result['compiler_warnings'])


if __name__ == '__main__':
    unittest.main()
