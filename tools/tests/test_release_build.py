from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import build_mac

class ReleaseBuildTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix='atode-release-build-')
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.artifacts = self.root / 'artifacts'
        self.artifacts.mkdir()
        self.debug = self.artifacts / 'ios-build-result.json'
        self.debug.write_text('{"build":"PASS","tests":"PASS","unit":69,"ui":9}')
        self.original = self.debug.read_bytes()
        self.commands = []
        for name, value in [('ROOT',self.root),('ARTIFACTS',self.artifacts)]:
            replacement = patch.object(build_mac,name,value)
            replacement.start()
            self.addCleanup(replacement.stop)

    def run_build(self, code=0, output=''):
        def execute(arguments, log_name):
            self.commands.append(arguments)
            return code if arguments[-1] == 'build' else 0, output if arguments[-1] == 'build' else ''
        with patch.object(build_mac.platform,'system',return_value='Darwin'), \
             patch.object(build_mac.shutil,'which',return_value='/usr/bin/xcodebuild'), \
             patch.object(build_mac,'generate'), patch.object(build_mac,'execute',side_effect=execute), \
             redirect_stdout(io.StringIO()):
            result = build_mac.main('build',simulator_signing=True,configuration='Release')
        self.assertEqual(self.debug.read_bytes(),self.original)
        return result,json.loads((self.artifacts/'ios-release-build-result.json').read_text())

    def testReleaseUsesSimulatorAndSeparateEvidenceWithoutChangingDebugAcceptance(self):
        code,result = self.run_build()
        self.assertEqual(code,0)
        self.assertEqual(result['build'],'PASS')
        self.assertEqual(result['tests'],'NOT_RUN')
        command = self.commands[-1]
        self.assertIn('Release',command)
        self.assertIn('generic/platform=iOS Simulator',command)
        self.assertIn('CODE_SIGN_IDENTITY=-',command)
        self.assertIn(str(self.root/'DerivedDataRelease'),command)
        self.assertNotIn('-allowProvisioningUpdates',command)

    def testReleaseFailureCannotReuseOldPass(self):
        (self.artifacts/'ios-release-build-result.json').write_text('{"build":"PASS"}')
        code,result = self.run_build(65,'error: deliberate build failure')
        self.assertEqual(code,1)
        self.assertEqual(result['build'],'FAIL')
        self.assertTrue(result['errors'])

    def testUnsupportedHostRecordsNotRunAndPreservesDebugEvidence(self):
        with patch.object(build_mac.platform,'system',return_value='Windows'),redirect_stdout(io.StringIO()):
            code = build_mac.main('build',configuration='Release')
        self.assertEqual(code,2)
        result = json.loads((self.artifacts/'ios-release-build-result.json').read_text())
        self.assertEqual(result['build'],'NOT_RUN')
        self.assertEqual(self.debug.read_bytes(),self.original)

if __name__ == '__main__':
    unittest.main()
