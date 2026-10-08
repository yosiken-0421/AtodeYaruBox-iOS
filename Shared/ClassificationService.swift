import Foundation

struct Classification: Equatable, Sendable {
    var action: ActionType
    var confidence: Double
    var evidence: [String]
}

enum ClassificationService {
    static func classify(_ text: String) -> Classification {
        // Keep rule work bounded for long shared text; the complete original is still saved.
        let value = String(text.prefix(100_000)).folding(options: [.caseInsensitive, .widthInsensitive],
                                                       locale: Locale(identifier: "ja_JP"))
        let rules: [(ActionType, [String])] = [
            (.returnItem, ["返品", "返送", "return deadline", "return label"]),
            (.payment, ["支払", "振込", "請求", "payment due", "invoice"]),
            (.reservation, ["予約", "予約番号", "reservation", "booking"]),
            (.reply, ["返信", "返事", "reply", "respond"]),
            (.contact, ["連絡", "電話する", "call back", "contact"]),
            (.event, ["開催", "会議", "開演", "集合", "meeting", "event"]),
            (.buy, ["購入", "買う", "買い物", "注文番号", "shopping", "buy"]),
            (.go, ["行く", "訪問", "アクセス", "住所", "visit"]),
            (.read, ["読む", "記事", "書籍", "read", "article"]),
            (.watch, ["見る", "観る", "動画", "映画", "watch", "video"]),
            (.reminder, ["忘れない", "期限", "締切", "remind", "deadline"])
        ]
        for (action, words) in rules {
            let matched = words.filter { word in
                if word.unicodeScalars.allSatisfy({ $0.isASCII }) {
                    let pattern = "\\b" + NSRegularExpression.escapedPattern(for: word) + "\\b"
                    return value.range(of: pattern, options: .regularExpression) != nil
                }
                return value.contains(word)
            }
            if !matched.isEmpty {
                return Classification(action: action, confidence: matched.count > 1 ? 0.85 : 0.65, evidence: matched)
            }
        }
        return Classification(action: .memo, confidence: 0.25, evidence: [])
    }
}
