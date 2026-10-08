import Foundation

enum SearchFilter: String, CaseIterable, Identifiable {
    case all, buy, go, reply, event, payment, reservation, read, hasDeadline, open, completed
    var id: String { rawValue }
    var label: String {
        switch self {
        case .all: return "すべて"
        case .buy: return "買う"
        case .go: return "行く"
        case .reply: return "返信"
        case .event: return "予定"
        case .payment: return "支払い"
        case .reservation: return "予約"
        case .read: return "読む"
        case .hasDeadline: return "期限あり"
        case .open: return "未完了"
        case .completed: return "完了"
        }
    }
}

enum SearchEngine {
    static func matches(_ item: InboxItem, query: String, filter: SearchFilter) -> Bool {
        guard item.status != .archived else { return false }
        switch filter {
        case .all: break
        case .hasDeadline: if item.dueDate == nil { return false }
        case .open: if !item.status.isOpen { return false }
        case .completed: if item.status != .completed { return false }
        default: if item.actionType.rawValue != filter.rawValue { return false }
        }
        let terms = normalize(query).split(whereSeparator: { $0.isWhitespace })
        if terms.isEmpty { return true }
        let fields = [item.title, item.note, item.rawOCRText, item.sourceURL ?? "",
                      item.extractedPlace ?? "", item.extractedProductName ?? "",
                      item.extractedOrderNumber ?? "", item.extractedReservationNumber ?? "",
                      item.extractedAddress ?? "", item.extractedPhone ?? "", item.extractedEmail ?? ""] + item.tags
        let value = normalize(fields.joined(separator: "\n"))
        return terms.allSatisfy { value.contains($0) }
    }
    private static func normalize(_ value: String) -> String {
        value.folding(options: [.caseInsensitive, .diacriticInsensitive, .widthInsensitive],
                      locale: Locale(identifier: "ja_JP"))
    }
}
