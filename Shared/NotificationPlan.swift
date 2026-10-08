import Foundation

struct ReminderSnapshot: Sendable {
    var id: UUID
    var title: String
    var dueDate: Date?
    var mode: ReminderMode
    var interval: TimeInterval
    var isOpen: Bool
    init(id: UUID, title: String, dueDate: Date?, mode: ReminderMode = .normal,
         interval: TimeInterval = 3600, isOpen: Bool = true) {
        self.id = id; self.title = title; self.dueDate = dueDate
        self.mode = mode; self.interval = interval; self.isOpen = isOpen
    }
}

struct PlannedNotification: Equatable, Sendable {
    var identifier: String
    var itemID: UUID
    var title: String
    var date: Date
    var mode: ReminderMode
}

enum NotificationPlan {
    // A deliberate app budget, leaving space for at most 16 location requests.
    static let timeBudget = 48
    static func make(items: [ReminderSnapshot], now: Date = Date(), limit: Int = timeBudget) -> [PlannedNotification] {
        var primary: [PlannedNotification] = []
        var repeats: [PlannedNotification] = []
        for item in items where item.isOpen {
            guard let due = item.dueDate else { continue }
            let interval = item.interval.isFinite ? max(item.interval, 3600) : 3600
            for index in 0...item.mode.repeatCount {
                let date = due.addingTimeInterval(Double(index) * interval)
                guard date > now else { continue }
                let entry = PlannedNotification(identifier: "time.\(item.id.uuidString).\(index)",
                    itemID: item.id, title: item.title, date: date, mode: item.mode)
                if index == 0 { primary.append(entry) } else { repeats.append(entry) }
            }
        }
        func sorted(_ values: [PlannedNotification]) -> [PlannedNotification] {
            values.sorted { $0.date == $1.date ? $0.identifier < $1.identifier : $0.date < $1.date }
        }
        let budget = min(max(limit, 0), timeBudget)
        // Give distinct items priority over extra alerts for one item.
        return Array((sorted(primary) + sorted(repeats)).prefix(budget))
    }
}
