"""Diagnose four genuine UI cases; this never certifies the complete release."""
import json
import os
from tools import build_mac
from tools.verify_native_result import read_cases

TARGETS = (
    'AtodeYaruBoxUITests/ExternalInputFlowTests/testPhotosPickerReadsSelectedScreenshotAndSearchesOCR',
    'AtodeYaruBoxUITests/SharingCalendarFlowTests',
)
EXPECTED = {
    'ExternalInputFlowTests.testPhotosPickerReadsSelectedScreenshotAndSearchesOCR',
    'SharingCalendarFlowTests.testCalendarAddsOnSelectedDayAndCompletesWithoutLeavingCalendar',
    'SharingCalendarFlowTests.testDarkLargestTextCalendarAndSharingRemainUsable',
    'SharingCalendarFlowTests.testSharingPreviewRequiresOptInAndOpensNativeShareSheet',
}


def main():
    original = build_mac.execute
    executions = []
    def focused(arguments, log_name, environment=None):
        if 'test-without-building' in arguments:
            if executions: raise ValueError('A diagnostic XCTest invocation must not be replayed')
            executions.append(True)
            arguments = arguments + ['-only-testing:' + target for target in TARGETS]
        return original(arguments, log_name, environment=environment)
    build_mac.execute = focused
    try:
        code = build_mac.main(scope='all', simulator_signing=True, external_input_qa=True)
    finally:
        build_mac.execute = original
    raw = json.loads((build_mac.ARTIFACTS / 'ios-build-result.json').read_text(encoding='utf-8'))
    text = '\n'.join((build_mac.ARTIFACTS / name).read_text(encoding='utf-8')
        for name in raw['logs'] if name.startswith('debug-test-') and name.endswith('.log'))
    cases = read_cases(text)
    passed = {name for name, values in cases.items() if values == ['passed']}
    ok = code == 0 and len(executions) == 1 and set(cases) == EXPECTED and passed == EXPECTED
    result = dict(kind='FOUR_CASE_DIAGNOSTIC_ONLY', status='PASS' if ok else 'FAIL',
        full_native_acceptance=False, expected=4, passed=len(passed & EXPECTED),
        source_sha=os.environ.get('GITHUB_SHA'), cases=cases)
    (build_mac.ARTIFACTS / 'native-focused-diagnostic.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))
    return 0 if ok else 1


if __name__ == '__main__': raise SystemExit(main())
