import XCTest
@testable import AtodeYaruBox

final class NotificationPlanTests: XCTestCase {
    private let now = Date(timeIntervalSince1970: 1_800_000_000)
    func testNoNotificationsForUndatedCompletedAndPastItems() {
        let items = [
            ReminderSnapshot(id: UUID(), title: "日付なし", dueDate: nil),
            ReminderSnapshot(id: UUID(), title: "済み", dueDate: now.addingTimeInterval(60), isOpen: false),
            ReminderSnapshot(id: UUID(), title: "期限切れ", dueDate: now.addingTimeInterval(-60))
        ]
        XCTAssertTrue(NotificationPlan.make(items: items, now: now).isEmpty)
    }
    func testModesAreFiniteAndNeverEarlierThanDue() {
        let due = now.addingTimeInterval(3600)
        for (mode, count) in [(ReminderMode.quiet, 1), (.normal, 1), (.strong, 2), (.persistent, 3)] {
            let item = ReminderSnapshot(id: UUID(), title: "予定", dueDate: due, mode: mode)
            let plan = NotificationPlan.make(items: [item], now: now)
            XCTAssertEqual(plan.count, count)
            XCTAssertTrue(plan.allSatisfy { $0.date >= due })
            XCTAssertEqual(Set(plan.map(\.identifier)).count, count)
        }
    }
    func testLargeDataCapsBudgetAndPrioritizesDifferentItems() {
        let items = (0..<1000).map {
            ReminderSnapshot(id: UUID(), title: "項目\($0)", dueDate: now.addingTimeInterval(Double($0 + 1) * 60), mode: .persistent)
        }
        let plan = NotificationPlan.make(items: items, now: now)
        XCTAssertEqual(plan.count, 48)
        XCTAssertEqual(Set(plan.map(\.itemID)).count, 48)
        XCTAssertEqual(plan.first?.date, now.addingTimeInterval(60))
        XCTAssertEqual(plan.last?.date, now.addingTimeInterval(48 * 60))
    }
    func testMalformedIntervalsAndNegativeBudgetAreSafe() {
        let item = ReminderSnapshot(id: UUID(), title: "予定", dueDate: now.addingTimeInterval(60), mode: .persistent, interval: .nan)
        let plan = NotificationPlan.make(items: [item], now: now)
        XCTAssertEqual(plan.count, 3)
        XCTAssertEqual(plan[1].date.timeIntervalSince(plan[0].date), 3600)
        XCTAssertTrue(NotificationPlan.make(items: [item], now: now, limit: -5).isEmpty)
        XCTAssertEqual(NotificationPlan.make(items: [item], now: now, limit: 999).count, 3)
    }
    func testLocationRejectsInvalidCoordinates() {
        XCTAssertTrue(LocationReminder(name: "店", latitude: 35, longitude: 139).isValid)
        XCTAssertFalse(LocationReminder(name: "不正", latitude: 91, longitude: 0).isValid)
        XCTAssertFalse(LocationReminder(name: "不正", latitude: .nan, longitude: 0).isValid)
        XCTAssertFalse(LocationReminder(name: "不正", latitude: 0, longitude: 0, radius: 10).isValid)
    }
}
