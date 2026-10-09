import XCTest
import AppIntents
import SwiftData
import UserNotifications
@testable import AtodeYaruBox

final class AppIntentIntegrationTests: XCTestCase {
    @MainActor func testSaveIntentPersistsURLAndNoteForIndependentHostReader() async throws {
        let marker = "IntentQA-" + UUID().uuidString
        var intent = SaveToBoxIntent()
        intent.title = marker
        intent.note = "あとで読む架空のページ"
        intent.url = "https://example.invalid/" + marker
        _ = try await intent.perform()
        let reader = try SharedStore.container(requireGroup: true)
        let repository = InboxRepository(context: reader.mainContext)
        let item = try XCTUnwrap(repository.all().first { $0.title == marker })
        defer {
            reader.mainContext.delete(item)
            try? reader.mainContext.save()
            NotificationScheduler.cancel(itemID: item.id)
        }
        XCTAssertEqual(item.note, intent.note ?? "")
        XCTAssertEqual(item.sourceURL, intent.url)
        XCTAssertEqual(item.sourceType, .url)
        XCTAssertTrue(item.status.isOpen)
        let other = try SharedStore.container(requireGroup: true)
        let persisted = try XCTUnwrap(InboxRepository(context: other.mainContext).find(item.id))
        XCTAssertEqual(persisted.title, marker)
        XCTAssertEqual(persisted.sourceURL, intent.url)
    }

    @MainActor func testInteractiveCompletionIntentUpdatesAnAlreadyOpenHostContext() async throws {
        let host = try SharedStore.container(requireGroup: true)
        let repository = InboxRepository(context: host.mainContext)
        let item = InboxItem(title: "架空のWidget完了 " + UUID().uuidString, dueDate: Date().addingTimeInterval(3600))
        try repository.insert(item)
        defer {
            host.mainContext.delete(item)
            try? host.mainContext.save()
            NotificationScheduler.cancel(itemID: item.id)
        }
        _ = try await CompleteItemIntent(itemID: item.id.uuidString).perform()
        try repository.refreshExternalChanges()
        XCTAssertEqual(item.status, .completed)
        let completedAt = try XCTUnwrap(item.completedAt)
        _ = try await CompleteItemIntent(itemID: item.id.uuidString).perform()
        try repository.refreshExternalChanges()
        XCTAssertEqual(item.completedAt, completedAt)
        let pending = await UNUserNotificationCenter.current().pendingNotificationRequests()
        XCTAssertFalse(pending.contains { $0.content.userInfo["itemID"] as? String == item.id.uuidString })
    }

    @MainActor func testNavigationIntentsRequestOneRouteWithoutSavingAnItem() async throws {
        let session = try XCTUnwrap(NotificationDelegate.session)
        let oldTab = session.selectedTab
        let oldComposer = session.showingComposer
        let preferences = try XCTUnwrap(UserDefaults(suiteName: SharedStore.groupID))
        let oldRoute = preferences.object(forKey: "pendingRoute")
        let oldDate = preferences.object(forKey: "pendingRouteDate")
        defer {
            session.selectedTab = oldTab
            session.showingComposer = oldComposer
            if let oldRoute { preferences.set(oldRoute, forKey: "pendingRoute") }
            else { preferences.removeObject(forKey: "pendingRoute") }
            if let oldDate { preferences.set(oldDate, forKey: "pendingRouteDate") }
            else { preferences.removeObject(forKey: "pendingRouteDate") }
        }
        let store = try SharedStore.container(requireGroup: true)
        let before = Set(try InboxRepository(context: store.mainContext).all().map(\.id))
        _ = try await OpenTodayIntent().perform()
        // RootView may already have consumed the notification synchronously.
        // The same host navigation path also consumes it when no view is listening.
        session.openPendingRoute()
        XCTAssertEqual(session.selectedTab, 1)
        XCTAssertNil(RouteStore.consume())
        _ = try await NewMemoIntent().perform()
        session.openPendingRoute()
        XCTAssertTrue(session.showingComposer)
        XCTAssertNil(RouteStore.consume())
        let after = Set(try InboxRepository(context: ModelContext(store)).all().map(\.id))
        XCTAssertEqual(before, after)
    }
}
