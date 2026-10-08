import Foundation
import SwiftData
import Observation

@Observable
@MainActor
final class AppSession {
    let container: ModelContainer
    let repository: InboxRepository
    let scheduler = NotificationScheduler()
    let calendar = CalendarService()
    let location = LocationReminderService()
    var items: [InboxItem] = []
    var selectedTab = 0
    var showingComposer = false
    var requestedItemID: UUID?
    var errorMessage: String?
    var noticeMessage: String?
    @ObservationIgnored private var reconcileTask: Task<Void, Never>?
    @ObservationIgnored private let externalEffectsEnabled: Bool

    init(container: ModelContainer,
         externalEffectsEnabled: Bool = !ProcessInfo.processInfo.arguments.contains("--ui-testing")) {
        self.container = container
        self.externalEffectsEnabled = externalEffectsEnabled
        self.repository = InboxRepository(context: container.mainContext)
        container.mainContext.autosaveEnabled = false
        do { items = try repository.all() } catch { errorMessage = error.localizedDescription }
        location.authorizationChanged = { [weak self] in self?.refreshSideEffects() }
    }

    func complete(_ item: InboxItem) {
        do { try repository.complete(item); refreshSideEffects() }
        catch { errorMessage = error.localizedDescription }
    }
    func snooze(_ item: InboxItem, until date: Date) async {
        do {
            try repository.snooze(item, until: date)
            await requestNotifications()
            refreshSideEffects()
        } catch { errorMessage = error.localizedDescription }
    }
    func reopen(_ item: InboxItem) {
        do { try repository.reopen(item); refreshSideEffects() }
        catch { errorMessage = error.localizedDescription }
    }
    func requestNotifications() async {
        guard externalEffectsEnabled else { return }
        do {
            if !(try await scheduler.requestIfNeeded()) { noticeMessage = AppError.notificationDenied.localizedDescription }
        } catch { noticeMessage = "保存しました。通知の設定を確認できませんでした。" }
    }
    func refreshSideEffects() {
        do { items = try repository.all() } catch { errorMessage = error.localizedDescription; return }
        guard externalEffectsEnabled else { return }
        reconcileTask?.cancel()
        reconcileTask = Task { [weak self] in
            guard let self else { return }
            do {
                try repository.refreshExternalChanges()
                let items = try repository.all()
                self.items = items
                // A missing group doesn't block the main app's local storage.
                if FileManager.default.containerURL(forSecurityApplicationGroupIdentifier: SharedStore.groupID) != nil {
                    try WidgetSnapshotService.write(items: items)
                }
                try await scheduler.reconcile(items: items)
            } catch {
                guard !Task.isCancelled else { return }
                noticeMessage = "項目は保存されています。通知またはウィジェットの更新に失敗しました。"
            }
        }
    }
    func openPendingRoute() {
        switch RouteStore.consume() {
        case "today": selectedTab = 1
        case "new": showingComposer = true
        default: break
        }
    }
}
