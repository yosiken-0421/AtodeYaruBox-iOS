import Foundation

enum InboxSection: String, CaseIterable, Identifiable {
    case overdue, today, needsReview, later, noDate
    var id: String { rawValue }
    var label: String {
        switch self {
        case .overdue: return "期限切れ"
        case .today: return "今日"
        case .needsReview: return "確認待ち"
        case .later: return "あとで"
        case .noDate: return "日付未設定"
        }
    }
    var symbol: String {
        switch self {
        case .overdue: return "exclamationmark.triangle"
        case .today: return "sun.max"
        case .needsReview: return "questionmark.circle"
        case .later: return "clock"
        case .noDate: return "calendar.badge.questionmark"
        }
    }
    static func section(for item: InboxItem, now: Date = Date(), calendar: Calendar = .current) -> InboxSection? {
        guard item.status.isOpen else { return nil }
        if let due = item.dueDate, due < now { return .overdue }
        if let due = item.dueDate, calendar.isDate(due, inSameDayAs: now) { return .today }
        if item.status == .inbox { return .needsReview }
        if item.dueDate != nil { return .later }
        return .noDate
    }
}
