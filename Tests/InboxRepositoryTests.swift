import XCTest
import SwiftData
@testable import AtodeYaruBox

final class InboxRepositoryTests: XCTestCase {
    @MainActor func testCreateAndFetchSurvivesNewContext() throws {
        let container = try SharedStore.container(inMemory: true)
        let repository = InboxRepository(context: container.mainContext)
        let item = InboxItem(title: "  本を読む  ", note: "第3章", actionType: .read)
        try repository.insert(item)
        let secondContext = ModelContext(container)
        let stored = try InboxRepository(context: secondContext).find(item.id)
        XCTAssertEqual(stored?.title, "本を読む")
        XCTAssertEqual(stored?.note, "第3章")
        XCTAssertEqual(stored?.status, .active)
    }
    @MainActor func testEmptyTitleIsRejectedWithoutSaving() throws {
        let container = try SharedStore.container(inMemory: true)
        let repository = InboxRepository(context: container.mainContext)
        XCTAssertThrowsError(try repository.insert(InboxItem(title: "　 \n")))
        XCTAssertTrue(try repository.all().isEmpty)
    }
    @MainActor func testCompleteAndReopenPersists() throws {
        let container = try SharedStore.container(inMemory: true)
        let repository = InboxRepository(context: container.mainContext)
        let item = InboxItem(title: "支払い", actionType: .payment)
        try repository.insert(item)
        let date = Date(timeIntervalSince1970: 1_800_000_000)
        try repository.complete(item, now: date)
        XCTAssertEqual(try repository.find(item.id)?.completedAt, date)
        XCTAssertFalse(item.status.isOpen)
        // A second Widget/Shortcut completion must not move the history timestamp.
        try repository.complete(item, now: date.addingTimeInterval(3600))
        let verification = InboxRepository(context: ModelContext(container))
        let completed = try XCTUnwrap(verification.find(item.id))
        XCTAssertEqual(completed.completedAt, date)
        XCTAssertEqual(completed.updatedAt, date)
        try repository.reopen(item)
        XCTAssertEqual(item.status, .active)
        XCTAssertNil(item.completedAt)
    }
    @MainActor func testSnoozePersistsDateAndStatus() throws {
        let container = try SharedStore.container(inMemory: true)
        let repository = InboxRepository(context: container.mainContext)
        let now = Date(timeIntervalSince1970: 1_800_000_000)
        let item = InboxItem(title: "電話する", now: now)
        try repository.insert(item)
        try repository.snooze(item, until: now.addingTimeInterval(3600), now: now)
        XCTAssertEqual(item.status, .snoozed)
        XCTAssertEqual(item.dueDate, now.addingTimeInterval(3600))
    }
    @MainActor func testCompletedItemCannotBeSnoozed() {
        let now = Date()
        let item = InboxItem(title: "済み")
        item.complete(now: now)
        item.snooze(until: now.addingTimeInterval(3600), now: now)
        XCTAssertEqual(item.status, .completed)
        XCTAssertNil(item.dueDate)
    }
    @MainActor func testPastSnoozeIsIgnored() {
        let now = Date()
        let item = InboxItem(title: "メモ")
        item.snooze(until: now.addingTimeInterval(-1), now: now)
        XCTAssertEqual(item.status, .active)
        XCTAssertNil(item.dueDate)
    }
    @MainActor func testLocationRoundTripAndUnknownEnumsAreSafe() {
        let item = InboxItem(title: "スーパー")
        let location = LocationReminder(name: "スーパー", latitude: 35.6, longitude: 139.7)
        item.locationReminder = location
        XCTAssertEqual(item.locationReminder, location)
        item.locationReminderData = Data("corrupt".utf8)
        XCTAssertNil(item.locationReminder)
        item.statusRaw = "future-status"
        item.actionTypeRaw = "future-type"
        XCTAssertEqual(item.status, .inbox)
        XCTAssertEqual(item.actionType, .other)
    }
    @MainActor func testExternalCompletionRefreshesExistingObject() throws {
        let container = try SharedStore.container(inMemory: true)
        let repository = InboxRepository(context: container.mainContext)
        let item = InboxItem(title: "共有項目", now: Date(timeIntervalSince1970: 100))
        try repository.insert(item)
        let external = InboxRepository(context: ModelContext(container))
        let externalItem = try XCTUnwrap(external.find(item.id))
        try external.complete(externalItem, now: Date(timeIntervalSince1970: 200))
        try repository.refreshExternalChanges()
        XCTAssertEqual(item.status, .completed)
        XCTAssertEqual(item.completedAt, Date(timeIntervalSince1970: 200))
    }
}
