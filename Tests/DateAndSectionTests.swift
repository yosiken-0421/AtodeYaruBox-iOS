import XCTest
@testable import AtodeYaruBox

final class DateAndSectionTests: XCTestCase {
    private var tokyo: Calendar {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = TimeZone(identifier: "Asia/Tokyo")!
        return calendar
    }
    private func date(_ hour: Int, _ minute: Int = 0, year: Int = 2026, month: Int = 10, day: Int = 6) -> Date {
        tokyo.date(from: DateComponents(year: year, month: month, day: day, hour: hour, minute: minute))!
    }
    func testEveningBeforeAndAfterCutoff() {
        XCTAssertEqual(SnoozeCalculator.date(for: .tonight, now: date(18), calendar: tokyo), date(19))
        XCTAssertEqual(SnoozeCalculator.date(for: .tonight, now: date(19), calendar: tokyo), date(19, day: 7))
        XCTAssertEqual(SnoozeCalculator.date(for: .tonight, now: date(23), calendar: tokyo), date(19, day: 7))
    }
    func testTomorrowMorningAndNight() {
        let now = date(23, 59)
        XCTAssertEqual(SnoozeCalculator.date(for: .tomorrowMorning, now: now, calendar: tokyo), date(8, day: 7))
        XCTAssertEqual(SnoozeCalculator.date(for: .tomorrowNight, now: now, calendar: tokyo), date(19, day: 7))
    }
    func testHourCrossesYearBoundary() {
        let now = date(23, 30, month: 12, day: 31)
        XCTAssertEqual(SnoozeCalculator.date(for: .hour, now: now, calendar: tokyo), date(0, 30, year: 2027, month: 1, day: 1))
    }
    func testDayPresetsPreserveWallClockAcrossDST() {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = TimeZone(identifier: "America/New_York")!
        let now = calendar.date(from: DateComponents(year: 2026, month: 3, day: 7, hour: 19))!
        let later = SnoozeCalculator.date(for: .threeDays, now: now, calendar: calendar)
        XCTAssertEqual(calendar.component(.hour, from: later), 19)
        XCTAssertEqual(calendar.component(.day, from: later), 10)
        XCTAssertEqual(SnoozeCalculator.date(for: .week, now: now, calendar: calendar).timeIntervalSince(now), 7 * 86400 - 3600)
    }
    @MainActor func testSectionsAreExclusiveAndCompletedItemsExcluded() {
        let now = date(12)
        let item = InboxItem(title: "項目", dueDate: date(11))
        item.status = .inbox
        XCTAssertEqual(InboxSection.section(for: item, now: now, calendar: tokyo), .overdue)
        item.dueDate = date(18)
        XCTAssertEqual(InboxSection.section(for: item, now: now, calendar: tokyo), .today)
        item.dueDate = nil
        XCTAssertEqual(InboxSection.section(for: item, now: now, calendar: tokyo), .needsReview)
        item.status = .active
        XCTAssertEqual(InboxSection.section(for: item, now: now, calendar: tokyo), .noDate)
        item.dueDate = date(12, day: 10)
        XCTAssertEqual(InboxSection.section(for: item, now: now, calendar: tokyo), .later)
        item.complete(now: now)
        XCTAssertNil(InboxSection.section(for: item, now: now, calendar: tokyo))
    }
}
