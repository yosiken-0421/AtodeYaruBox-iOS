import Foundation
import UniformTypeIdentifiers

extension UTType {
    static let atodeTask = UTType("jp.atodeyarubox.item") ?? UTType(exportedAs: "jp.atodeyarubox.item", conformingTo: .json)
}

/// A copy of the fields the sender selected, without persistence IDs or private attachment paths.
struct SharedTaskDocument: Codable, Identifiable, Sendable {
    var id = UUID()
    var format = "atodeyarubox.item"
    var version = 1
    var title: String
    var note: String
    var action: ActionType
    var dueDate: Date?
    var sourceURL: String?

    enum CodingKeys: String, CodingKey { case format, version, title, note, action, dueDate, sourceURL }
}

enum SharedTaskCodec {
    static let maximumBytes = 64 * 1024
    static func validate(_ document: SharedTaskDocument) throws {
        guard document.format == "atodeyarubox.item", document.version == 1,
              !document.title.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
              document.title.count <= 160, document.note.utf8.count <= 32 * 1024 else { throw AppError.invalidFile }
        if let url = document.sourceURL {
            guard url.utf8.count <= 4096, URLValidator.webURL(url) != nil else { throw AppError.invalidURL }
        }
        if let date = document.dueDate {
            let seconds = date.timeIntervalSince1970
            guard seconds.isFinite, (-2208988800...7258118400).contains(seconds) else { throw AppError.invalidFile }
        }
    }
    static func encode(_ document: SharedTaskDocument) throws -> Data {
        try validate(document)
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        let data = try encoder.encode(document)
        guard data.count <= maximumBytes else { throw AppError.sharedFileTooLarge }
        return data
    }
    static func decode(_ data: Data) throws -> SharedTaskDocument {
        guard data.count <= maximumBytes else { throw AppError.sharedFileTooLarge }
        let decoder = JSONDecoder(); decoder.dateDecodingStrategy = .iso8601
        do {
            let result = try decoder.decode(SharedTaskDocument.self, from: data)
            try validate(result)
            return result
        } catch let error as AppError { throw error }
        catch { throw AppError.invalidFile }
    }
    static func text(_ document: SharedTaskDocument, locale: Locale = .current, timeZone: TimeZone = .current) -> String {
        var lines = [document.title, "種類：" + document.action.label]
        if let date = document.dueDate {
            let formatter = DateFormatter(); formatter.locale = locale; formatter.timeZone = timeZone
            formatter.dateStyle = .medium; formatter.timeStyle = .short
            lines.append("日時：" + formatter.string(from: date))
        }
        if !document.note.isEmpty { lines.append(document.note) }
        if let url = document.sourceURL { lines.append(url) }
        return lines.joined(separator: "\n")
    }
}
