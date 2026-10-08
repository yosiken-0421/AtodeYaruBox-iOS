import Foundation

enum ItemStatus: String, Codable, CaseIterable, Sendable {
    case inbox, active, snoozed, completed, archived
    var isOpen: Bool { self != .completed && self != .archived }
}

enum SourceType: String, Codable, Sendable {
    case memo, photo, camera, url, text, pdf, file
}

enum ActionType: String, Codable, CaseIterable, Identifiable, Sendable {
    case buy, go, reply, event, reminder, payment, reservation
    case read, watch, contact, returnItem, memo, other
    var id: String { rawValue }
    var label: String {
        switch self {
        case .buy: return "買う"
        case .go: return "行く"
        case .reply: return "返信"
        case .event: return "予定"
        case .reminder: return "忘れない"
        case .payment: return "支払う"
        case .reservation: return "予約"
        case .read: return "読む"
        case .watch: return "見る"
        case .contact: return "連絡"
        case .returnItem: return "返品"
        case .memo: return "メモ"
        case .other: return "その他"
        }
    }
    var symbol: String {
        switch self {
        case .buy: return "cart"
        case .go: return "map"
        case .reply: return "arrowshape.turn.up.left"
        case .event: return "calendar"
        case .reminder: return "bell"
        case .payment: return "creditcard"
        case .reservation: return "ticket"
        case .read: return "book"
        case .watch: return "play.rectangle"
        case .contact: return "phone"
        case .returnItem: return "shippingbox"
        case .memo: return "note.text"
        case .other: return "tray"
        }
    }
}

enum ReminderMode: String, Codable, CaseIterable, Identifiable, Sendable {
    case quiet, normal, strong, persistent
    var id: String { rawValue }
    var label: String {
        switch self {
        case .quiet: return "静か"
        case .normal: return "普通"
        case .strong: return "強め"
        case .persistent: return "絶対忘れない"
        }
    }
    var repeatCount: Int {
        switch self {
        case .quiet, .normal: return 0
        case .strong: return 1
        case .persistent: return 2
        }
    }
}

struct LocationReminder: Codable, Equatable, Sendable {
    var name: String
    var latitude: Double
    var longitude: Double
    var radius: Double = 200
    var onEntry: Bool = true
    var isValid: Bool {
        latitude.isFinite && longitude.isFinite && radius.isFinite
            && (-90...90).contains(latitude) && (-180...180).contains(longitude)
            && (100...1000).contains(radius)
    }
}

enum AppError: LocalizedError {
    case emptyTitle, invalidURL, invalidFile, fileTooLarge, missingAppGroup, invalidSnoozeDate
    case notificationDenied, locationDenied, locationUnavailable, invalidLocation
    case staleItem
    var errorDescription: String? {
        switch self {
        case .emptyTitle: return "タイトルを入力してください。"
        case .invalidSnoozeDate: return "あとで知らせる日時は、今より後に設定してください。"
        case .invalidURL: return "http または https で始まるWebページのURLを入力してください。"
        case .invalidFile: return "このファイルは読み込めません。別のファイルをお試しください。"
        case .fileTooLarge: return "ファイルは25MB以下で保存してください。"
        case .missingAppGroup: return "共有用の保存場所を開けませんでした。項目はまだ保存されていません。アプリの「追加」からメモや写真を保存できます。"
        case .notificationDenied: return "保存しました。通知を使う場合はiPhoneの設定で通知を許可してください。"
        case .locationDenied: return "場所の通知には位置情報の許可が必要です。日時の通知は引き続き使えます。"
        case .locationUnavailable: return "この端末では場所の通知を利用できません。"
        case .invalidLocation: return "選んだ場所を使えませんでした。別の場所を選び直してください。"
        case .staleItem: return "この項目は見つかりません。箱を開き直してください。"
        }
    }
}

enum URLValidator {
    static func webURL(_ text: String) -> URL? {
        guard let url = URL(string: text.trimmingCharacters(in: .whitespacesAndNewlines)),
              let scheme = url.scheme?.lowercased(), ["http", "https"].contains(scheme),
              let host = url.host, !host.isEmpty, url.user == nil, url.password == nil else { return nil }
        return url
    }
}
