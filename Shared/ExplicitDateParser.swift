import Foundation

enum ExplicitDateParser {
    static func parse(_ text: String, now: Date, calendar: Calendar) -> Date? {
        // Numeric OCR years are Gregorian; a display-calendar preference must
        // not reinterpret 2030 as a Japanese era year or a Buddhist year.
        var parsingCalendar = Calendar(identifier: .gregorian)
        parsingCalendar.timeZone = calendar.timeZone
        // Explicit numeric dates only; do not guess ambiguous natural language.
        // Vision can omit the space between a date and a clock. Extra digits
        // remain invalid unless followed by an explicit colon or Japanese hour.
        let pattern = #"(?<![\d/\-])(?:(\d{4})\s*(?:年|/|\-)\s*)?(\d{1,2})\s*(?:月|/|\-)\s*(\d{1,2})(?:日)?(?:(?![\d/\-])|(?=[0-9]{1,2}[:時]))"#
        guard let regex = try? NSRegularExpression(pattern: pattern),
              let match = regex.firstMatch(in: text, range: NSRange(text.startIndex..., in: text)),
              let dateRange = Range(match.range, in: text) else { return nil }
        func number(_ group: Int) -> Int? {
            guard let range = Range(match.range(at: group), in: text) else { return nil }
            return Int(text[range])
        }
        let prefix = String(text[..<dateRange.lowerBound])
        if number(1) == nil, prefix.range(of: #"(?:[0-9]+|元|来|去|再来)\s*年\s*$"#, options: .regularExpression) != nil {
            return nil // An unsupported explicit year is not an omitted year.
        }
        let year = number(1) ?? parsingCalendar.component(.year, from: now)
        guard let month = number(2), let day = number(3), (1...12).contains(month), (1...31).contains(day) else { return nil }
        var hour = 9
        var minute = 0
        let remaining = String(text[dateRange.upperBound...])
        // Parse time separately so regex backtracking cannot turn an invalid clock
        // into a date-only 9:00 candidate. Colon times require explicit minutes.
        let clockPattern = #"^[ T　]*([0-9]+)[\t 　]*([:時])[\t 　]*([0-9]*)(?:分)?"#
        if let clock = try? NSRegularExpression(pattern: clockPattern),
           let time = clock.firstMatch(in: remaining, range: NSRange(remaining.startIndex..., in: remaining)),
           let hourRange = Range(time.range(at: 1), in: remaining),
           let separatorRange = Range(time.range(at: 2), in: remaining),
           let minuteRange = Range(time.range(at: 3), in: remaining) {
            let hourText = String(remaining[hourRange])
            let minuteText = String(remaining[minuteRange])
            guard hourText.count <= 2, minuteText.count <= 2, let parsedHour = Int(hourText),
                  remaining[separatorRange] != ":" || !minuteText.isEmpty else { return nil }
            hour = parsedHour
            minute = minuteText.isEmpty ? 0 : (Int(minuteText) ?? 60)
            let tailStart = Range(time.range, in: remaining)?.upperBound ?? remaining.endIndex
            let tail = String(remaining[tailStart...].prefix(while: { !$0.isNewline }))
            // Unsupported AM/PM notation must not silently become a 24-hour value.
            if tail.range(of: #"^[\t 　]*(?:AM|PM)\b"#, options: [.regularExpression, .caseInsensitive]) != nil { return nil }
        } else {
            let sameLine = String(remaining.prefix(while: { !$0.isNewline }))
            if sameLine.range(of: #"[0-9]+[\t 　]*[:：時]|午前|午後|\b(?:AM|PM)\b"#,
                              options: [.regularExpression, .caseInsensitive]) != nil { return nil }
        }
        guard (0...23).contains(hour), (0...59).contains(minute) else { return nil }
        let parts = DateComponents(year: year, month: month, day: day, hour: hour, minute: minute)
        guard let date = parsingCalendar.date(from: parts) else { return nil }
        let checked = parsingCalendar.dateComponents([.year, .month, .day, .hour, .minute], from: date)
        guard checked.year == year, checked.month == month, checked.day == day,
              checked.hour == hour, checked.minute == minute else { return nil }
        return date
    }
}
