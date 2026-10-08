import Foundation

struct ExtractedFields: Sendable {
    var date: Date?
    var returnDeadline: Date?
    var url: String?
    var phone: String?
    var email: String?
    var price: String?
    var address: String?
    var place: String?
    var productName: String?
    var orderNumber: String?
    var reservationNumber: String?
}

enum OCRParser {
    static func parse(_ raw: String, now: Date = Date(), calendar: Calendar = .current) -> ExtractedFields {
        // Bound detector work. The full original text is separately persisted and searchable.
        let text = String(raw.prefix(100_000)).precomposedStringWithCompatibilityMapping
        var fields = ExtractedFields()
        fields.email = capture(#"([A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,})"#, in: text)
        fields.price = capture(#"((?:¥|￥)\s*[0-9][0-9,]*(?:\.[0-9]+)?|[0-9][0-9,]*\s*円)"#, in: text)
        fields.orderNumber = capture(#"(?:注文番号|注文ID|order\s*(?:number|no\.?|id))\s*[:：#]?\s*([A-Z0-9][A-Z0-9\-]{2,})"#, in: text)
        fields.reservationNumber = capture(#"(?:予約番号|予約ID|(?:reservation|booking)\s*(?:number|no\.?|id))\s*[:：#]?\s*([A-Z0-9][A-Z0-9\-]{2,})"#, in: text)
        fields.place = capture(#"(?:店名|店舗名|会場|場所)\s*[:：]\s*([^\n\r]+)"#, in: text)
        fields.productName = capture(#"(?:商品名|品名)\s*[:：]\s*([^\n\r]+)"#, in: text)
        let types = NSTextCheckingResult.CheckingType.link.rawValue
            | NSTextCheckingResult.CheckingType.phoneNumber.rawValue
            | NSTextCheckingResult.CheckingType.address.rawValue
        if let detector = try? NSDataDetector(types: types) {
            for result in detector.matches(in: text, range: NSRange(text.startIndex..., in: text)) {
                if result.resultType == .link, let url = result.url,
                   URLValidator.webURL(url.absoluteString) != nil, fields.url == nil {
                    fields.url = url.absoluteString
                }
                if result.resultType == .phoneNumber, fields.phone == nil { fields.phone = result.phoneNumber }
                if result.resultType == .address, fields.address == nil,
                   let range = Range(result.range, in: text) { fields.address = String(text[range]) }
            }
        }
        if fields.address == nil {
            fields.address = capture(#"(?:住所|所在地)\s*[:：]\s*([^\n\r]+)"#, in: text)
        }
        fields.date = explicitDate(in: text, now: now, calendar: calendar)
        for line in text.components(separatedBy: .newlines)
            where line.contains("返品期限") || line.lowercased().contains("return deadline") {
            fields.returnDeadline = explicitDate(in: line, now: now, calendar: calendar)
        }
        return fields
    }

    static func explicitDate(in text: String, now: Date, calendar: Calendar) -> Date? {
        ExplicitDateParser.parse(text, now: now, calendar: calendar)
    }

    private static func capture(_ pattern: String, in text: String) -> String? {
        guard let regex = try? NSRegularExpression(pattern: pattern, options: .caseInsensitive),
              let result = regex.firstMatch(in: text, range: NSRange(text.startIndex..., in: text)),
              let range = Range(result.range(at: 1), in: text) else { return nil }
        return String(text[range]).trimmingCharacters(in: .whitespacesAndNewlines)
    }
}
