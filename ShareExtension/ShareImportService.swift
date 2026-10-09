import Foundation
import UIKit
import UniformTypeIdentifiers

struct ShareDraft: Identifiable {
    var id = UUID()
    var title: String
    var note = ""
    var source: SourceType
    var url: String?
    var asset: StoredAsset?
    var rawText = ""
    var fields = ExtractedFields()
    var action: ActionType = .memo
    var confidence = 0.25
}

@MainActor
enum ShareImportService {
    static func read(_ provider: NSItemProvider) async throws -> ShareDraft {
        if provider.hasItemConformingToTypeIdentifier(UTType.url.identifier) {
            let url = try await readURL(provider)
            if url.isFileURL {
                return try await fileDraft(bytes: readLimited(url), type: UTType(filenameExtension: url.pathExtension) ?? .data,
                                            title: url.deletingPathExtension().lastPathComponent)
            }
            guard URLValidator.webURL(url.absoluteString) != nil else { throw AppError.invalidURL }
            return ShareDraft(title: url.host ?? "Webページ", source: .url, url: url.absoluteString, action: .read)
        }
        let types = provider.registeredTypeIdentifiers.compactMap { UTType($0) }
        if let type = types.first(where: { $0.conforms(to: .image) || $0.conforms(to: .pdf) }) {
            let bytes: Data = try await withCheckedThrowingContinuation { continuation in
                provider.loadDataRepresentation(forTypeIdentifier: type.identifier) { data, error in
                    if let error { continuation.resume(throwing: error) }
                    else if let data { continuation.resume(returning: data) }
                    else { continuation.resume(throwing: AppError.invalidFile) }
                }
            }
            return try await fileDraft(bytes: bytes, type: type, title: provider.suggestedName ?? "共有したファイル")
        }
        if provider.hasItemConformingToTypeIdentifier(UTType.text.identifier) {
            let text = try await readText(provider)
            guard text.utf8.count <= AssetStore.maximumBytes else { throw AppError.fileTooLarge }
            var draft = ShareDraft(title: String(text.split(whereSeparator: { $0.isNewline }).first?.prefix(120) ?? ""),
                                   note: text, source: .text, rawText: text)
            analyze(&draft)
            return draft
        }
        guard let type = types.first(where: { $0.conforms(to: .data) }) else { throw AppError.invalidFile }
        let bytes: Data = try await withCheckedThrowingContinuation { continuation in
            provider.loadFileRepresentation(forTypeIdentifier: type.identifier) { url, error in
                if let error { continuation.resume(throwing: error) }
                else if let url {
                    // Copy inside this callback: temporary provider files expire when it returns.
                    do { continuation.resume(returning: try readLimited(url)) }
                    catch { continuation.resume(throwing: error) }
                } else { continuation.resume(throwing: AppError.invalidFile) }
            }
        }
        return try await fileDraft(bytes: bytes, type: type, title: provider.suggestedName ?? "共有したファイル")
    }

    private static func readURL(_ provider: NSItemProvider) async throws -> URL {
        if provider.canLoadObject(ofClass: NSURL.self) {
            return try await withCheckedThrowingContinuation { continuation in
                provider.loadObject(ofClass: NSURL.self) { object, error in
                    if let error { continuation.resume(throwing: error) }
                    else if let url = object as? NSURL { continuation.resume(returning: url as URL) }
                    else { continuation.resume(throwing: AppError.invalidURL) }
                }
            }
        }
        return try await withCheckedThrowingContinuation { continuation in
            provider.loadItem(forTypeIdentifier: UTType.url.identifier, options: nil) { item, error in
                if let error { continuation.resume(throwing: error) }
                else if let url = item as? URL { continuation.resume(returning: url) }
                else if let text = item as? String, let url = URL(string: text) { continuation.resume(returning: url) }
                else if let data = item as? Data, data.count <= AssetStore.maximumBytes,
                        let text = String(data: data, encoding: .utf8), let url = URL(string: text) {
                    continuation.resume(returning: url)
                } else { continuation.resume(throwing: AppError.invalidURL) }
            }
        }
    }

    private static func readText(_ provider: NSItemProvider) async throws -> String {
        if provider.canLoadObject(ofClass: NSString.self) {
            return try await withCheckedThrowingContinuation { continuation in
                provider.loadObject(ofClass: NSString.self) { object, error in
                    if let error { continuation.resume(throwing: error) }
                    else if let text = object as? NSString { continuation.resume(returning: text as String) }
                    else { continuation.resume(throwing: AppError.invalidFile) }
                }
            }
        }
        let type = provider.registeredTypeIdentifiers.first { UTType($0)?.conforms(to: .text) == true } ?? UTType.text.identifier
        return try await withCheckedThrowingContinuation { continuation in
            provider.loadItem(forTypeIdentifier: type, options: nil) { item, error in
                if let error { continuation.resume(throwing: error) }
                else if let text = item as? String { continuation.resume(returning: text) }
                else if let text = item as? NSAttributedString { continuation.resume(returning: text.string) }
                else if let data = item as? Data, data.count <= AssetStore.maximumBytes,
                        let text = String(data: data, encoding: .utf8) { continuation.resume(returning: text) }
                else { continuation.resume(throwing: AppError.invalidFile) }
            }
        }
    }

    nonisolated private static func readLimited(_ url: URL) throws -> Data {
        let size = try url.resourceValues(forKeys: [.fileSizeKey]).fileSize ?? AssetStore.maximumBytes + 1
        guard size <= AssetStore.maximumBytes else { throw AppError.fileTooLarge }
        return try BoundedFileReader.read(url, maximumBytes: AssetStore.maximumBytes)
    }
    private static func fileDraft(bytes: Data, type: UTType, title: String) async throws -> ShareDraft {
        let asset = try AssetStore.save(bytes, type: type, requireGroup: true)
        var draft = ShareDraft(title: title, source: type.conforms(to: .image) ? .photo : (type.conforms(to: .pdf) ? .pdf : .file), asset: asset)
        if type.conforms(to: .image) { draft.rawText = (try? await OCRService.recognize(data: bytes)) ?? "" }
        else if type.conforms(to: .pdf) { draft.rawText = (try? await OCRService.recognizePDF(data: bytes)) ?? "" }
        analyze(&draft)
        return draft
    }
    private static func analyze(_ draft: inout ShareDraft) {
        draft.fields = OCRParser.parse(draft.rawText)
        let result = ClassificationService.classify(draft.rawText)
        draft.action = result.action; draft.confidence = result.confidence
        if draft.url == nil { draft.url = draft.fields.url }
    }
    static func item(from draft: ShareDraft) throws -> InboxItem {
        guard !draft.title.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { throw AppError.emptyTitle }
        let item = InboxItem(title: draft.title, note: draft.note, sourceType: draft.source, actionType: draft.action)
        item.status = .inbox
        item.sourceURL = draft.url; item.localAssetPath = draft.asset?.path; item.thumbnailPath = draft.asset?.thumbnailPath
        item.rawOCRText = draft.rawText; item.confidence = draft.confidence
        item.extractedPrice = draft.fields.price; item.extractedPlace = draft.fields.place
        item.extractedProductName = draft.fields.productName; item.extractedAddress = draft.fields.address
        item.extractedPhone = draft.fields.phone; item.extractedEmail = draft.fields.email
        item.extractedOrderNumber = draft.fields.orderNumber; item.extractedReservationNumber = draft.fields.reservationNumber
        item.extractedReturnDeadline = draft.fields.returnDeadline
        // Shared date candidates are reviewed in the host app, not silently scheduled by the extension.
        return item
    }
}
