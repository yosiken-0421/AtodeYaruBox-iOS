from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
import tempfile
import unittest

from tools import verify_release_result as verifier

class ReleaseEvidenceTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix='atode-release-evidence-')
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.artifacts = self.root/'artifacts'
        self.artifacts.mkdir()
        self.now = datetime.now(timezone.utc)
        self.raw = {'configuration':'Release','scope':'build','build':'PASS','build_exit_code':0,
            'tests':'NOT_RUN','errors':[],'warnings':[],'logs':['release-build-fixture.log'],
            'started_at':(self.now-timedelta(minutes=5)).isoformat(),
            'finished_at':(self.now-timedelta(minutes=1)).isoformat()}
        (self.artifacts/'release-build-fixture.log').write_text('Synthetic host evidence. No Xcode executed.')
        app = self.root/'DerivedDataRelease/Build/Products/Release-iphonesimulator/AtodeYaruBox.app'
        for suffix in ['AtodeYaruBox','Info.plist','PrivacyInfo.xcprivacy','PlugIns/BoxShare.appex/Info.plist','PlugIns/BoxWidgets.appex/Info.plist']:
            path = app/suffix
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text('Synthetic host fixture')

    def inspect(self):
        (self.artifacts/'ios-release-build-result.json').write_text(json.dumps(self.raw))
        return verifier.inspect(self.root,self.now)

    def testSeparateCompleteFreshReleaseEvidencePassesWithoutClaimingDeviceDistribution(self):
        report = self.inspect()
        self.assertEqual(report['status'],'PASS')
        self.assertFalse(report['device_distribution_verified'])

    def testStaleAndDebugEvidenceAreRejected(self):
        self.raw['finished_at'] = (self.now-timedelta(hours=2)).isoformat()
        self.assertEqual(self.inspect()['status'],'FAIL')
        self.raw['finished_at'] = (self.now-timedelta(minutes=1)).isoformat()
        self.raw['configuration'] = 'Debug'
        self.assertEqual(self.inspect()['status'],'FAIL')

    def testZeroExitCannotHideErrorCompilerWarningOrMissingProduct(self):
        self.raw['errors'] = ['error: failed archive generation']
        self.assertEqual(self.inspect()['status'],'FAIL')
        self.raw['errors'] = []
        self.raw['warnings'] = ['Shared/BoxColors.swift:5:8: warning: fixture warning']
        self.assertEqual(self.inspect()['status'],'FAIL')
        self.raw['warnings'] = []
        target = self.root/'DerivedDataRelease/Build/Products/Release-iphonesimulator/AtodeYaruBox.app/PlugIns/BoxWidgets.appex/Info.plist'
        target.unlink()
        self.assertEqual(self.inspect()['status'],'FAIL')

    def testParentPathAndMissingLogsAreRejected(self):
        self.raw['logs'] = ['../release-fixture.log']
        self.assertEqual(self.inspect()['status'],'FAIL')
        self.raw['logs'] = ['missing.log']
        self.assertEqual(self.inspect()['status'],'FAIL')

if __name__ == '__main__':
    unittest.main()
