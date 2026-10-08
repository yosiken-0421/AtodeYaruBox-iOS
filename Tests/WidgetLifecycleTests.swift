import XCTest
import SwiftData
@testable import AtodeYaruBox

final class WidgetLifecycleTests: XCTestCase {
    private var tokyo: Calendar {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = TimeZone(identifier: "Asia/Tokyo")!
        return calendar
    }

    @MainActor func testDeadlineChangesCountsWithoutAnotherHostWrite() throws {
        let store = try SharedStore.container(inMemory: true)
        let repository = InboxRepository(context: store.mainContext)
        let before = try XCTUnwrap(tokyo.date(from: DateComponents(year: 2030, month: 10, day: 7, hour: 18, minute: 59)))
        let due = before.addingTimeInterval(60)
        let item = InboxItem(title: String(repeating: "大切な情報", count: 100), dueDate: due)
        item.rawOCRText = String(repeating: "原文を残す", count: 30000)
        try repository.insert(item)
        try repository.insert(InboxItem(title: "いつか確認するメモ"))
        let completed = InboxItem(title: "完了済み", dueDate: due)
        completed.complete()
        try repository.insert(completed)
        let archived = InboxItem(title: "アーカイブ済み", dueDate: due)
        archived.status = .archived
        try repository.insert(archived)
        let first = try WidgetStoreQueries.snapshot(context: ModelContext(store), now: before, calendar: tokyo)
        XCTAssertEqual(first.openCount, 2)
        XCTAssertEqual(first.overdueCount, 0)
        XCTAssertEqual(first.today.map(\.id), [item.id])
        let after = try WidgetStoreQueries.snapshot(context: ModelContext(store), now: due.addingTimeInterval(1), calendar: tokyo)
        XCTAssertEqual(after.openCount, 2)
        XCTAssertEqual(after.overdueCount, 1)
        XCTAssertEqual(after.next?.id, item.id)
        XCTAssertEqual(after.today.first?.title.count, 160)
        let original = try XCTUnwrap(InboxRepository(context: ModelContext(store)).find(item.id))
        XCTAssertEqual(original.title.count, 500)
        XCTAssertEqual(original.rawOCRText, item.rawOCRText)
    }

    @MainActor func testMidnightRecomputesTodayWithoutChangingSavedItems() throws {
        let store = try SharedStore.container(inMemory: true)
        let repository = InboxRepository(context: store.mainContext)
        let before = try XCTUnwrap(tokyo.date(from: DateComponents(year: 2030, month: 10, day: 7, hour: 23, minute: 59)))
        let yesterday = InboxItem(title: "前日の項目", dueDate: before.addingTimeInterval(-60))
        let today = InboxItem(title: "新しい日の項目", dueDate: before.addingTimeInterval(120))
        try repository.insert(yesterday)
        try repository.insert(today)
        let first = try WidgetStoreQueries.snapshot(context: ModelContext(store), now: before, calendar: tokyo)
        XCTAssertEqual(first.today.map(\.id), [yesterday.id])
        XCTAssertEqual(first.overdueCount, 1)
        let afterTime = before.addingTimeInterval(180)
        let after = try WidgetStoreQueries.snapshot(context: ModelContext(store), now: afterTime, calendar: tokyo)
        XCTAssertEqual(after.today.map(\.id), [today.id])
        XCTAssertEqual(after.overdueCount, 2)
        XCTAssertEqual(after.openCount, 2)
        XCTAssertEqual(after.generatedAt, afterTime)
    }

    @MainActor func testTimelineIncludesDeadlineAndMidnightWithoutUnboundedEntries() throws {
        let store = try SharedStore.container(inMemory: true)
        let repository = InboxRepository(context: store.mainContext)
        let now = try XCTUnwrap(tokyo.date(from: DateComponents(year: 2030, month: 10, day: 7, hour: 23, minute: 50)))
        for index in 0..<20 {
            try repository.insert(InboxItem(title: "通知候補 \(index)", dueDate: now.addingTimeInterval(Double(index + 1) * 60)))
        }
        let snapshots = try WidgetStoreQueries.timeline(context: ModelContext(store), now: now, calendar: tokyo)
        XCTAssertLessThanOrEqual(snapshots.count, 15)
        XCTAssertEqual(snapshots.first?.overdueCount, 0)
        XCTAssertEqual(snapshots.last?.overdueCount, 20)
        let midnight = try XCTUnwrap(tokyo.date(byAdding: .day, value: 1, to: tokyo.startOfDay(for: now)))
        let changedDay = try XCTUnwrap(snapshots.first { $0.generatedAt == midnight })
        XCTAssertTrue(changedDay.today.allSatisfy { item in
            item.dueDate.map { tokyo.isDate($0, inSameDayAs: midnight) } ?? false
        })
        XCTAssertEqual(snapshots[1].generatedAt, now.addingTimeInterval(61))
        XCTAssertEqual(snapshots[1].overdueCount, 1)
    }
}
