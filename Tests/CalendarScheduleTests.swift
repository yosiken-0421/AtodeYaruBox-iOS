import XCTest
@testable import AtodeYaruBox

final class CalendarScheduleTests: XCTestCase {
    private var calendar: Calendar {
        var result = Calendar(identifier: .gregorian); result.timeZone = TimeZone(identifier: "Asia/Tokyo")!
        result.locale = Locale(identifier: "ja_JP"); result.firstWeekday = 1; return result
    }
    private func date(_ year: Int, _ month: Int, _ day: Int, _ hour: Int = 9, _ minute: Int = 0) -> Date {
        calendar.date(from: DateComponents(year: year, month: month, day: day, hour: hour, minute: minute))!
    }
    func testLeapFebruaryAndMonthPaddingFollowCalendar() {
        let result = CalendarMonth(containing: date(2028, 2, 18), calendar: calendar)
        XCTAssertEqual(result.days.count, 29); XCTAssertEqual(result.leadingEmptyDays, 2)
        XCTAssertEqual(result.days.last?.number, 29); XCTAssertEqual(result.weekdayLabels.count, 7)
    }
    func testDifferentFirstWeekdayAndDecemberRollover() {
        var monday = calendar; monday.firstWeekday = 2
        XCTAssertEqual(CalendarMonth(containing: date(2028, 2, 18), calendar: monday).leadingEmptyDays, 1)
        let december = CalendarMonth(containing: date(2027, 12, 31), calendar: calendar)
        let next = calendar.date(byAdding: .month, value: 1, to: december.start)!
        XCTAssertEqual(calendar.component(.year, from: next), 2028)
        XCTAssertEqual(CalendarMonth(containing: next, calendar: calendar).days.count, 31)
    }
    func testCountsExcludeCompletedArchivedAndUndatedByDefault() {
        let due = date(2028, 2, 5)
        let values = [ItemStatus.active, .inbox, .snoozed, .completed, .archived].map { ScheduledEntry(id: UUID(), dueDate: due, status: $0) }
            + [ScheduledEntry(id: UUID(), dueDate: nil, status: .active)]
        XCTAssertEqual(CalendarSchedule.counts(values, in: due, calendar: calendar)[calendar.startOfDay(for: due)], 3)
        XCTAssertEqual(CalendarSchedule.counts(values, in: due, completed: true, calendar: calendar)[calendar.startOfDay(for: due)], 4)
    }
    func testDayOrderingAndMonthBoundaryDoNotMixDates() {
        let first = UUID(), last = UUID()
        let values = [ScheduledEntry(id: last, dueDate: date(2028, 3, 1, 20), status: .active),
                      ScheduledEntry(id: UUID(), dueDate: date(2028, 2, 29, 23), status: .active),
                      ScheduledEntry(id: first, dueDate: date(2028, 3, 1, 8), status: .active)]
        XCTAssertEqual(CalendarSchedule.identifiers(values, on: date(2028, 3, 1), calendar: calendar), [first, last])
        XCTAssertEqual(CalendarSchedule.counts(values, in: date(2028, 2, 1), calendar: calendar).values.reduce(0,+), 1)
    }
    func testDSTUsesCalendarDaysRatherThanTwentyFourHours() {
        var zone = Calendar(identifier: .gregorian); zone.timeZone = TimeZone(identifier: "America/Los_Angeles")!
        let date = zone.date(from: DateComponents(year: 2028, month: 3, day: 12, hour: 12))!
        let model = CalendarMonth(containing: date, calendar: zone)
        XCTAssertEqual(model.days.count, 31)
        let interval = zone.dateInterval(of: .day, for: date)!
        XCTAssertEqual(interval.duration, 23 * 3600)
        let value = ScheduledEntry(id: UUID(), dueDate: interval.end.addingTimeInterval(-1), status: .active)
        XCTAssertEqual(CalendarSchedule.identifiers([value], on: date, calendar: zone), [value.id])
    }
    func testLargeScheduleAndEmptyMonthStayDeterministic() {
        let due = date(2028, 2, 5)
        let values = (0..<10000).map { _ in ScheduledEntry(id: UUID(), dueDate: due, status: .active) }
        XCTAssertEqual(CalendarSchedule.counts(values, in: due, calendar: calendar)[calendar.startOfDay(for: due)], 10000)
        XCTAssertTrue(CalendarSchedule.counts(values, in: date(2028, 3, 1), calendar: calendar).isEmpty)
    }
    func testAddingLateAtNightStaysOnSelectedDay() {
        let now = date(2028, 2, 5, 23, 50)
        let result = CalendarSchedule.dateForNewItem(on: now, now: now, calendar: calendar)
        XCTAssertTrue(calendar.isDate(result, inSameDayAs: now)); XCTAssertGreaterThan(result, now)
        XCTAssertEqual(CalendarSchedule.dateForNewItem(on: date(2028, 2, 6), now: now, calendar: calendar), date(2028, 2, 6, 9))
    }
}
