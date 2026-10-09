import XCTest
import UserNotifications
@testable import AtodeYaruBox

/// Uses the Simulator's notification daemon, not a mock or only a date calculation.
final class NotificationIntegrationTests: XCTestCase {
    @MainActor private func authorize() async throws -> UNUserNotificationCenter {
        let center = UNUserNotificationCenter.current()
        // Test host only: provisional authorization does not present a permission alert.
        // The production app continues to request normal permission when needed.
        let granted = try await center.requestAuthorization(options: [.alert, .sound, .badge, .provisional])
        XCTAssertTrue(granted, "Simulator notification authorization failed")
        NotificationScheduler.registerActions()
        return center
    }

    @MainActor func testSaveSnoozeScheduleAndCompleteCancelsRealRequest() async throws {
        let center = try await authorize()
        let session = AppSession(container: try SharedStore.container(inMemory: true), externalEffectsEnabled: false)
        let item = InboxItem(title: "通知の検証")
        defer { NotificationScheduler.cancel(itemID: item.id) }
        try session.repository.insert(item)
        let now = Date()
        let due = now.addingTimeInterval(3600)
        try session.repository.snooze(item, until: due, now: now)
        try await session.scheduler.reconcile(items: [item], now: now)
        let requests = await center.pendingNotificationRequests()
        let request = try XCTUnwrap(requests.first { $0.identifier == "time.\(item.id.uuidString).0" })
        let trigger = try XCTUnwrap(request.trigger as? UNCalendarNotificationTrigger)
        let next = try XCTUnwrap(trigger.nextTriggerDate())
        XCTAssertEqual(next.timeIntervalSince(due), 0, accuracy: 1)
        XCTAssertFalse(trigger.repeats)
        XCTAssertEqual(request.content.userInfo["itemID"] as? String, item.id.uuidString)
        XCTAssertEqual(request.content.categoryIdentifier, NotificationScheduler.categoryID)
        XCTAssertEqual(trigger.dateComponents.calendar?.identifier, .gregorian)

        // Real OS registration of a date created with Buddhist year numbering.
        // It must remain the same instant after conversion, not a year in the far future.
        let zone = try XCTUnwrap(TimeZone(identifier: "Asia/Tokyo"))
        var buddhist = Calendar(identifier: .buddhist)
        buddhist.timeZone = zone
        let year = Calendar(identifier: .gregorian).component(.year, from: now) + 1
        let alternativeDue = try XCTUnwrap(buddhist.date(from: DateComponents(year: year + 543, month: 10, day: 9, hour: 8)))
        let alternativeID = "time.\(item.id.uuidString).1"
        let alternativeTrigger = NotificationScheduler.trigger(for: alternativeDue, timeZone: zone)
        try await center.add(UNNotificationRequest(identifier: alternativeID, content: request.content, trigger: alternativeTrigger))
        let alternativeRequests = await center.pendingNotificationRequests()
        let alternativeRequest = try XCTUnwrap(alternativeRequests.first { $0.identifier == alternativeID })
        let storedTrigger = try XCTUnwrap(alternativeRequest.trigger as? UNCalendarNotificationTrigger)
        let storedNext = try XCTUnwrap(storedTrigger.nextTriggerDate())
        XCTAssertEqual(storedNext.timeIntervalSince(alternativeDue), 0, accuracy: 1)
        try session.repository.complete(item)
        let after = await center.pendingNotificationRequests()
        XCTAssertFalse(after.contains { $0.identifier.contains(item.id.uuidString) })
        XCTAssertEqual(item.status, .completed)
    }

    @MainActor func testLargeInboxIsBoundedByRealNotificationCenter() async throws {
        let center = try await authorize()
        let now = Date()
        let items = (0..<100).map { index -> InboxItem in
            let item = InboxItem(title: "大量データ \(index)", dueDate: now.addingTimeInterval(3600 + Double(index) * 60))
            item.reminderMode = .persistent
            return item
        }
        defer { for item in items { NotificationScheduler.cancel(itemID: item.id) } }
        let scheduler = NotificationScheduler()
        try await scheduler.reconcile(items: items, now: now)
        let requests = await center.pendingNotificationRequests().filter { $0.identifier.hasPrefix("time.") }
        XCTAssertEqual(requests.count, 48)
        let settings = await center.notificationSettings()
        let expectedLevel: UNNotificationInterruptionLevel = settings.timeSensitiveSetting == .enabled ? .timeSensitive : .active
        XCTAssertTrue(requests.allSatisfy { $0.content.interruptionLevel == expectedLevel })
        let identifiers = Set(items.map { $0.id.uuidString })
        XCTAssertTrue(requests.allSatisfy { identifiers.contains($0.content.userInfo["itemID"] as? String ?? "") })
        XCTAssertEqual(Set(requests.compactMap { $0.content.userInfo["itemID"] as? String }).count, 48)
    }

    @MainActor func testNotificationActionsAreRegisteredWithJapaneseTitles() async throws {
        let center = try await authorize()
        let categories = await center.notificationCategories()
        let category = try XCTUnwrap(categories.first { $0.identifier == NotificationScheduler.categoryID })
        XCTAssertEqual(category.actions.map(\.identifier), [NotificationScheduler.completeAction,
            NotificationScheduler.hourAction, NotificationScheduler.tomorrowAction])
        XCTAssertEqual(category.actions.map(\.title), ["完了", "1時間後", "明日"])
        XCTAssertTrue(category.actions.allSatisfy { $0.options.contains(.authenticationRequired) })
    }
}
