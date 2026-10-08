import XCTest
@testable import AtodeYaruBox

final class ExplicitDateParserTests: XCTestCase {
    private var calendar: Calendar {
        var value = Calendar(identifier: .gregorian)
        value.timeZone = TimeZone(identifier: "Asia/Tokyo")!
        return value
    }
    private var now: Date {
        calendar.date(from: DateComponents(year: 2026, month: 10, day: 6))!
    }
    func testMalformedClockCannotBecomeDateOnlyCandidate() {
        for text in ["2026/10/06 14:999", "2026/10/06 999:30", "2026/10/06 14:",
                     "2026年10月6日 14時999分", "2026/10/06 25:30", "2026/10/06 14:99",
                     "2026/10/06 午後5時", "2026/10/06 at 5:00 PM", "2026/10/06 5:00 PM", "2026/10/06 - 14:30"] {
            XCTAssertNil(ExplicitDateParser.parse(text, now: now, calendar: calendar), text)
        }
    }
    func testJapaneseHourOnlyIsExplicitAndColonRequiresMinutes() throws {
        let value = try XCTUnwrap(ExplicitDateParser.parse("2026年10月6日 14時", now: now, calendar: calendar))
        XCTAssertEqual(calendar.component(.hour, from: value), 14)
        XCTAssertEqual(calendar.component(.minute, from: value), 0)
        XCTAssertNil(ExplicitDateParser.parse("2026/10/06 14:", now: now, calendar: calendar))
    }
    func testMissingYearAndTimeUseDocumentedDefaults() throws {
        let value = try XCTUnwrap(ExplicitDateParser.parse("10月9日", now: now, calendar: calendar))
        XCTAssertEqual(calendar.component(.year, from: value), 2026)
        XCTAssertEqual(calendar.component(.hour, from: value), 9)
        for identifier in [Calendar.Identifier.japanese, .buddhist] {
            var displayCalendar = Calendar(identifier: identifier)
            displayCalendar.timeZone = calendar.timeZone
            XCTAssertEqual(ExplicitDateParser.parse("10月9日", now: now, calendar: displayCalendar), value)
        }
    }
    func testLeapDayAndNumericBoundaries() {
        XCTAssertNotNil(ExplicitDateParser.parse("2028/02/29", now: now, calendar: calendar))
        for text in ["2026/02/29", "2026/10/066", "電話 03-1234-5678", "日付未定",
                     "8/10/9", "R8/10/9", "令和8年10月9日", "令和元年10月9日", "12345年10月9日", "来年10月9日"] {
            XCTAssertNil(ExplicitDateParser.parse(text, now: now, calendar: calendar), text)
        }
    }
    func testNonexistentDaylightSavingClockIsRejected() {
        var eastern = Calendar(identifier: .gregorian)
        eastern.timeZone = TimeZone(identifier: "America/New_York")!
        XCTAssertNil(ExplicitDateParser.parse("2026/03/08 02:30", now: now, calendar: eastern))
    }

    func testOCRJoinedDateAndClockPreserveExactTime() {
        let expected = calendar.date(from: DateComponents(year: 2030, month: 10, day: 9, hour: 8, minute: 0))
        for text in ["2030/10/0908:00", "2030-10-0908:00", "2030年10月9日08時00分"] {
            XCTAssertEqual(ExplicitDateParser.parse(text, now: now, calendar: calendar), expected, text)
            for identifier in [Calendar.Identifier.japanese, .buddhist] {
                var displayCalendar = Calendar(identifier: identifier)
                displayCalendar.timeZone = calendar.timeZone
                XCTAssertEqual(ExplicitDateParser.parse(text, now: now, calendar: displayCalendar), expected, text)
            }
        }
    }

    func testMalformedJoinedClockAndExtraDigitsRemainRejected() {
        for text in ["2030/10/0908:", "2030/10/0925:00", "2030/10/0908:999",
                     "2030/10/09099:00", "2030/10/099", "2030/02/3008:00"] {
            XCTAssertNil(ExplicitDateParser.parse(text, now: now, calendar: calendar), text)
        }
    }
}
