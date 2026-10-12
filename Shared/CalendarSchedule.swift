import Foundation

struct ScheduledEntry: Sendable {
    let id: UUID
    let dueDate: Date?
    let status: ItemStatus
}

struct CalendarDay: Identifiable, Sendable {
    let date: Date
    let number: Int
    var id: Date { date }
}

struct CalendarMonth {
    let start: Date
    let days: [CalendarDay]
    let leadingEmptyDays: Int
    let weekdayLabels: [String]

    init(containing date: Date, calendar: Calendar = .current) {
        let monthStart = calendar.dateInterval(of: .month, for: date)?.start ?? calendar.startOfDay(for: date)
        start = monthStart
        let range = calendar.range(of: .day, in: .month, for: monthStart) ?? 1..<2
        days = range.compactMap { number in
            calendar.date(byAdding: .day, value: number - 1, to: monthStart).map { CalendarDay(date: $0, number: number) }
        }
        leadingEmptyDays = (calendar.component(.weekday, from: monthStart) - calendar.firstWeekday + 7) % 7
        let symbols = calendar.shortStandaloneWeekdaySymbols
        weekdayLabels = (0..<7).map { symbols[(calendar.firstWeekday - 1 + $0) % 7] }
    }
}

enum CalendarSchedule {
    static func includes(_ status: ItemStatus, completed: Bool) -> Bool {
        status.isOpen || (completed && status == .completed)
    }

    static func counts(_ entries: [ScheduledEntry], in month: Date, completed: Bool = false,
                       calendar: Calendar = .current) -> [Date: Int] {
        guard let interval = calendar.dateInterval(of: .month, for: month) else { return [:] }
        var result: [Date: Int] = [:]
        for entry in entries where includes(entry.status, completed: completed) {
            if let due = entry.dueDate, interval.contains(due) {
                result[calendar.startOfDay(for: due), default: 0] += 1
            }
        }
        return result
    }

    static func identifiers(_ entries: [ScheduledEntry], on day: Date, completed: Bool = false,
                            calendar: Calendar = .current) -> [UUID] {
        entries.filter {
            includes($0.status, completed: completed) && $0.dueDate.map { calendar.isDate($0, inSameDayAs: day) } == true
        }.sorted {
            if $0.dueDate == $1.dueDate { return $0.id.uuidString < $1.id.uuidString }
            return ($0.dueDate ?? .distantFuture) < ($1.dueDate ?? .distantFuture)
        }.map(\.id)
    }

    static func dateForNewItem(on day: Date, now: Date = Date(), calendar: Calendar = .current) -> Date {
        if calendar.isDate(day, inSameDayAs: now) {
            let end = calendar.dateInterval(of: .day, for: now)?.end ?? now.addingTimeInterval(3600)
            return max(now, min(now.addingTimeInterval(3600), end.addingTimeInterval(-1)))
        }
        return calendar.date(bySettingHour: 9, minute: 0, second: 0, of: day) ?? day
    }
}
