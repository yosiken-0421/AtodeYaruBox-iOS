import Foundation

@MainActor
enum NotificationActionService {
    @discardableResult
    static func apply(identifier: String, itemID: UUID, repository: InboxRepository,
                      now: Date = Date(), calendar: Calendar = .current) throws -> Bool {
        guard [NotificationScheduler.completeAction, NotificationScheduler.hourAction,
               NotificationScheduler.tomorrowAction].contains(identifier) else { return false }
        // The app may already have an older registered object when a Widget or
        // Shortcut completes the same item in its separate shared-store context.
        try repository.refreshExternalChanges()
        guard let item = try repository.find(itemID), item.status.isOpen else {
            NotificationScheduler.cancel(itemID: itemID)
            return false
        }
        switch identifier {
        case NotificationScheduler.completeAction:
            try repository.complete(item, now: now)
        case NotificationScheduler.hourAction:
            try repository.snooze(item, until: SnoozeCalculator.date(for: .hour, now: now, calendar: calendar), now: now)
        case NotificationScheduler.tomorrowAction:
            try repository.snooze(item, until: SnoozeCalculator.date(for: .tomorrowMorning, now: now, calendar: calendar), now: now)
        default: return false
        }
        return true
    }
}
