import Foundation
import UserNotifications
import CoreLocation

@MainActor
final class NotificationScheduler {
    static let categoryID = "INBOX_REMINDER"
    static let completeAction = "COMPLETE"
    static let hourAction = "HOUR"
    static let tomorrowAction = "TOMORROW"
    private let center = UNUserNotificationCenter.current()
    private var generation = 0

    static func registerActions() {
        let actions = [
            UNNotificationAction(identifier: completeAction, title: "完了", options: []),
            UNNotificationAction(identifier: hourAction, title: "1時間後", options: []),
            UNNotificationAction(identifier: tomorrowAction, title: "明日", options: [])
        ]
        UNUserNotificationCenter.current().setNotificationCategories([
            UNNotificationCategory(identifier: categoryID, actions: actions, intentIdentifiers: [], options: [])
        ])
    }

    func requestIfNeeded() async throws -> Bool {
        let settings = await center.notificationSettings()
        switch settings.authorizationStatus {
        case .notDetermined: return try await center.requestAuthorization(options: [.alert, .sound, .badge])
        case .authorized, .provisional, .ephemeral: return true
        default: return false
        }
    }

    func reconcile(items: [InboxItem], now: Date = Date()) async throws {
        generation += 1
        let currentGeneration = generation
        let snapshots = items.map { ReminderSnapshot(id: $0.id, title: $0.title, dueDate: $0.dueDate,
            mode: $0.reminderMode, interval: $0.reminderInterval, isOpen: $0.status.isOpen) }
        let locations = items.filter { $0.status.isOpen && $0.locationReminder?.isValid == true }
            .sorted { ($0.dueDate ?? .distantFuture) < ($1.dueDate ?? .distantFuture) }
            .prefix(16).compactMap { item -> (UUID, String, ReminderMode, LocationReminder)? in
                guard let location = item.locationReminder else { return nil }
                return (item.id, item.title, item.reminderMode, location)
            }
        let settings = await center.notificationSettings()
        guard currentGeneration == generation else { return }
        let pending = await center.pendingNotificationRequests()
        guard currentGeneration == generation else { return }
        guard [.authorized, .provisional, .ephemeral].contains(settings.authorizationStatus) else {
            center.removePendingNotificationRequests(withIdentifiers: pending.filter { Self.isOwned($0.identifier) }.map(\.identifier))
            return
        }
        let plans = NotificationPlan.make(items: snapshots, now: now)
        let locationAllowed = CLLocationManager().authorizationStatus == .authorizedAlways
        let desiredLocations = locationAllowed ? locations : []
        let desired = Set(plans.map(\.identifier) + desiredLocations.map { "location.\($0.0.uuidString)" })
        center.removePendingNotificationRequests(withIdentifiers: pending.filter {
            Self.isOwned($0.identifier) && !desired.contains($0.identifier)
        }.map(\.identifier))
        for plan in plans {
            guard currentGeneration == generation, !Task.isCancelled else { return }
            let content = Self.content(title: plan.title, id: plan.itemID, mode: plan.mode)
            let trigger = Self.trigger(for: plan.date)
            try await center.add(UNNotificationRequest(identifier: plan.identifier, content: content, trigger: trigger))
        }
        for (id, title, mode, location) in desiredLocations {
            guard currentGeneration == generation, !Task.isCancelled else { return }
            let region = CLCircularRegion(center: CLLocationCoordinate2D(latitude: location.latitude, longitude: location.longitude),
                radius: location.radius, identifier: id.uuidString)
            region.notifyOnEntry = location.onEntry
            region.notifyOnExit = !location.onEntry
            try await center.add(UNNotificationRequest(identifier: "location.\(id.uuidString)",
                content: Self.content(title: title, id: id, mode: mode),
                trigger: UNLocationNotificationTrigger(region: region, repeats: false)))
        }
    }

    static func trigger(for date: Date, timeZone: TimeZone = .current) -> UNCalendarNotificationTrigger {
        // A stored Date is an absolute instant. Interpret all extracted units in
        // the same explicit calendar, even when the user's UI uses Japanese/Buddhist years.
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = timeZone
        var components = calendar.dateComponents([.era, .year, .month, .day, .hour, .minute, .second], from: date)
        components.calendar = calendar
        components.timeZone = timeZone
        return UNCalendarNotificationTrigger(dateMatching: components, repeats: false)
    }

    static func cancel(itemID: UUID) {
        let identifiers = (0...2).map { "time.\(itemID.uuidString).\($0)" } + ["location.\(itemID.uuidString)"]
        let center = UNUserNotificationCenter.current()
        center.removePendingNotificationRequests(withIdentifiers: identifiers)
        center.removeDeliveredNotifications(withIdentifiers: identifiers)
    }
    private static func isOwned(_ id: String) -> Bool { id.hasPrefix("time.") || id.hasPrefix("location.") }
    private static func content(title: String, id: UUID, mode: ReminderMode) -> UNMutableNotificationContent {
        let content = UNMutableNotificationContent()
        // Generic lock-screen text by default; the title stays on the device and inside the app.
        content.title = "あとでやる箱"
        let preferences = UserDefaults(suiteName: SharedStore.groupID) ?? .standard
        content.body = preferences.bool(forKey: "showNotificationTitles") ? title : "あとでやることがあります。"
        content.categoryIdentifier = categoryID
        content.userInfo = ["itemID": id.uuidString]
        if mode != .quiet { content.sound = .default }
        if mode == .strong || mode == .persistent { content.interruptionLevel = .timeSensitive }
        return content
    }
}
