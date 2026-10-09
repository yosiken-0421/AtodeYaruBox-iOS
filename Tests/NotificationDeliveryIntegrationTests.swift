import XCTest
import UserNotifications
@testable import AtodeYaruBox

final class NotificationDeliveryIntegrationTests: XCTestCase {
    @MainActor private func authorizedCenter() async throws -> UNUserNotificationCenter {
        let center = UNUserNotificationCenter.current()
        let allowed = try await center.requestAuthorization(options: [.alert, .sound, .badge, .provisional])
        XCTAssertTrue(allowed)
        NotificationScheduler.registerActions()
        return center
    }

    @MainActor private func delivered(_ identifier: String, center: UNUserNotificationCenter) async throws -> UNNotification? {
        for _ in 0..<24 {
            if let notification = await center.deliveredNotifications().first(where: { $0.request.identifier == identifier }) {
                return notification
            }
            try await Task.sleep(for: .milliseconds(500))
        }
        return nil
    }

    @MainActor func testScheduledReminderIsDeliveredAndCompletionRemovesIt() async throws {
        let center = try await authorizedCenter()
        let store = try SharedStore.container(inMemory: true)
        let repository = InboxRepository(context: store.mainContext)
        let due = Date(timeIntervalSince1970: floor(Date().timeIntervalSince1970) + 6)
        let item = InboxItem(title: "架空の通知配送テスト " + UUID().uuidString, dueDate: due)
        item.reminderMode = .quiet
        try repository.insert(item)
        defer { NotificationScheduler.cancel(itemID: item.id) }
        let identifier = "time.\(item.id.uuidString).0"
        try await NotificationScheduler().reconcile(items: [item])
        let candidate = try await delivered(identifier, center: center)
        let notification = try XCTUnwrap(candidate)
        XCTAssertEqual(notification.request.content.userInfo["itemID"] as? String, item.id.uuidString)
        XCTAssertEqual(notification.request.content.categoryIdentifier, NotificationScheduler.categoryID)
        XCTAssertNil(notification.request.content.sound)
        XCTAssertTrue(item.status.isOpen, "OS delivery alone must not complete the saved item")
        try repository.complete(item)
        var removed = false
        for _ in 0..<20 {
            let remaining = await center.deliveredNotifications()
            if !remaining.contains(where: { $0.request.identifier == identifier }) {
                removed = true
                break
            }
            try await Task.sleep(for: .milliseconds(100))
        }
        XCTAssertTrue(removed, "Completion must remove the delivered reminder from Notification Center")
        XCTAssertEqual(item.status, .completed)
    }

    @MainActor func testCompletionBeforeDeadlinePreventsDelivery() async throws {
        let center = try await authorizedCenter()
        let store = try SharedStore.container(inMemory: true)
        let repository = InboxRepository(context: store.mainContext)
        let due = Date(timeIntervalSince1970: floor(Date().timeIntervalSince1970) + 6)
        let item = InboxItem(title: "架空の取消テスト " + UUID().uuidString, dueDate: due)
        try repository.insert(item)
        defer { NotificationScheduler.cancel(itemID: item.id) }
        let identifier = "time.\(item.id.uuidString).0"
        try await NotificationScheduler().reconcile(items: [item])
        let pending = await center.pendingNotificationRequests()
        XCTAssertTrue(pending.contains { $0.identifier == identifier })
        try repository.complete(item)
        try await Task.sleep(for: .seconds(8))
        let notifications = await center.deliveredNotifications()
        XCTAssertFalse(notifications.contains { $0.request.identifier == identifier })
        let after = await center.pendingNotificationRequests()
        XCTAssertFalse(after.contains { $0.identifier == identifier })
    }
}
