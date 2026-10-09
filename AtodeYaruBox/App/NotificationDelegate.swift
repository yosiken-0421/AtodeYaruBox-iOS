import UIKit
import UserNotifications

@MainActor
final class NotificationDelegate: NSObject, UIApplicationDelegate, UNUserNotificationCenterDelegate {
    static weak var session: AppSession?

    func application(_ application: UIApplication, didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil) -> Bool {
        AppAppearance.configure()
        NotificationScheduler.registerActions()
        UNUserNotificationCenter.current().delegate = self
        return true
    }

    nonisolated func userNotificationCenter(_ center: UNUserNotificationCenter,
        willPresent notification: UNNotification, withCompletionHandler completionHandler: @escaping @Sendable (UNNotificationPresentationOptions) -> Void) {
        completionHandler(notification.request.content.sound == nil ? [.list] : [.banner, .list, .sound])
    }

    nonisolated func userNotificationCenter(_ center: UNUserNotificationCenter,
        didReceive response: UNNotificationResponse) async {
        let identifier = response.notification.request.content.userInfo["itemID"] as? String
        let action = response.actionIdentifier
        await Self.handleResponse(identifier: identifier, action: action)
    }

    private static func handleResponse(identifier: String?, action: String) async {
            guard let identifier, let id = UUID(uuidString: identifier) else { return }
            do {
                let activeSession: AppSession
                if let session = Self.session { activeSession = session }
                else { activeSession = AppSession(container: try SharedStore.container()) }
                if action == UNNotificationDefaultActionIdentifier {
                    try activeSession.repository.refreshExternalChanges()
                    guard try activeSession.repository.find(id) != nil else { return }
                    activeSession.requestedItemID = id
                    activeSession.selectedTab = 0
                } else {
                    _ = try NotificationActionService.apply(identifier: action, itemID: id,
                                                            repository: activeSession.repository)
                }
                let items = try activeSession.repository.all()
                if FileManager.default.containerURL(forSecurityApplicationGroupIdentifier: SharedStore.groupID) != nil {
                    try WidgetSnapshotService.write(items: items)
                }
                try await activeSession.scheduler.reconcile(items: items)
            } catch {
                Self.session?.errorMessage = "通知の操作を保存できませんでした。箱で項目を確認してください。"
            }
    }
}
