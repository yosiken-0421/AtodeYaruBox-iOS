import Foundation

enum SnoozeOption: String, CaseIterable, Identifiable {
    case hour, tonight, tomorrowMorning, tomorrowNight, threeDays, week
    var id: String { rawValue }
    var label: String {
        switch self {
        case .hour: return "1時間後"
        case .tonight: return "今日の夜"
        case .tomorrowMorning: return "明日の朝"
        case .tomorrowNight: return "明日の夜"
        case .threeDays: return "3日後"
        case .week: return "1週間後"
        }
    }
}

enum SnoozeCalculator {
    static func date(for option: SnoozeOption, now: Date = Date(),
                     calendar: Calendar = .current) -> Date {
        switch option {
        case .hour: return now.addingTimeInterval(3600)
        case .tonight:
            // At or after 19:00, use tomorrow at 19:00, never a past reminder.
            return calendar.nextDate(after: now,
                matching: DateComponents(hour: 19, minute: 0, second: 0),
                matchingPolicy: .nextTime, repeatedTimePolicy: .first) ?? now.addingTimeInterval(3600)
        case .tomorrowMorning: return tomorrow(hour: 8, now: now, calendar: calendar)
        case .tomorrowNight: return tomorrow(hour: 19, now: now, calendar: calendar)
        case .threeDays: return calendar.date(byAdding: .day, value: 3, to: now) ?? now.addingTimeInterval(259200)
        case .week: return calendar.date(byAdding: .day, value: 7, to: now) ?? now.addingTimeInterval(604800)
        }
    }
    private static func tomorrow(hour: Int, now: Date, calendar: Calendar) -> Date {
        let day = calendar.date(byAdding: .day, value: 1, to: calendar.startOfDay(for: now)) ?? now
        return calendar.date(bySettingHour: hour, minute: 0, second: 0, of: day) ?? day
    }
}
