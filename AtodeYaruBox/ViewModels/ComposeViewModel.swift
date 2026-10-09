import Foundation
import Observation
import UniformTypeIdentifiers

@Observable
@MainActor
final class ComposeViewModel {
    var title = ""
    var note = ""
    var urlText = ""
    var action: ActionType = .memo
    var hasDate = false
    var dueDate = SnoozeCalculator.date(for: .tonight)
    var reminderMode: ReminderMode = .normal
    var tagsText = ""
    var rawOCRText = ""
    var source: SourceType = .memo
    var asset: StoredAsset?
    var extracted = ExtractedFields()
    var isProcessing = false
    var isSaving = false
    var errorMessage: String?
    var importMessage: String?
    var confidence: Double = 1
    private var saved = false
    private var automaticTitle: String?
    private var automaticURL: String?
    private var automaticAction: ActionType?
    private var automaticDate: Date?

    init() {
        reminderMode = ReminderMode(rawValue: UserDefaults.standard.string(forKey: "defaultReminderMode") ?? "normal") ?? .normal
    }

    var canSave: Bool { !title.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && !isProcessing && !isSaving }

    func importData(_ data: Data, type: UTType, source: SourceType) async {
        guard !isProcessing else { return }
        isProcessing = true
        defer { isProcessing = false }
        do {
            try Task.checkCancellation()
            let newAsset = try AssetStore.save(data, type: type)
            if let asset { AssetStore.remove(asset) }
            asset = newAsset
            self.source = source
            resetAutomaticAnalysis()
            do {
                if type.conforms(to: .image) { rawOCRText = try await OCRService.recognize(data: data) }
                else if type.conforms(to: .pdf) {
                    rawOCRText = try await OCRService.recognizePDF(data: data)
                    importMessage = "PDFは先頭10ページまで文字を読み取ります。元のファイルはそのまま保存します。"
                } else if type.conforms(to: .text) { rawOCRText = String(data: data, encoding: .utf8) ?? "" }
                applyAnalysis()
                if rawOCRText.isEmpty { importMessage = "文字を読み取れませんでした。タイトルを付けて保存できます。" }
            } catch {
                importMessage = "文字を読み取れませんでした。元の画像・ファイルは保存できます。"
            }
            if Task.isCancelled { discardUnsavedAsset(); return }
            if title.isEmpty {
                title = source == .photo || source == .camera ? "写真から保存" : "ファイルから保存"
                automaticTitle = title
            }
        } catch { errorMessage = error.localizedDescription }
    }

    func importFile(_ url: URL) async {
        let accessing = url.startAccessingSecurityScopedResource()
        defer { if accessing { url.stopAccessingSecurityScopedResource() } }
        do {
            let size = try url.resourceValues(forKeys: [.fileSizeKey]).fileSize ?? AssetStore.maximumBytes + 1
            guard size <= AssetStore.maximumBytes else { throw AppError.fileTooLarge }
            let type = UTType(filenameExtension: url.pathExtension) ?? .data
            await importData(try BoundedFileReader.read(url, maximumBytes: AssetStore.maximumBytes), type: type, source: type.conforms(to: .pdf) ? .pdf : .file)
            if title == "ファイルから保存", automaticTitle == title {
                title = url.deletingPathExtension().lastPathComponent
                automaticTitle = title
            }
        } catch { errorMessage = error.localizedDescription }
    }

    private func applyAnalysis() {
        guard !rawOCRText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return }
        extracted = OCRParser.parse(rawOCRText)
        let classification = ClassificationService.classify(rawOCRText)
        action = classification.action
        automaticAction = action
        confidence = classification.confidence
        if title.isEmpty {
            title = String(rawOCRText.split(whereSeparator: { $0.isNewline }).first?.prefix(120) ?? "")
            automaticTitle = title
        }
        if urlText.isEmpty {
            urlText = extracted.url ?? ""
            automaticURL = urlText
        }
        if let date = extracted.returnDeadline ?? extracted.date {
            dueDate = date; hasDate = true; automaticDate = date
        }
    }

    private func resetAutomaticAnalysis() {
        // A replacement attachment must never inherit OCR fields from the old file.
        // Keep values the user has edited instead of replacing them with suggestions.
        if title == automaticTitle { title = "" }
        if urlText == automaticURL { urlText = "" }
        if action == automaticAction { action = .memo }
        if hasDate, dueDate == automaticDate {
            hasDate = false; dueDate = SnoozeCalculator.date(for: .tonight)
        }
        rawOCRText = ""
        extracted = ExtractedFields()
        confidence = 1
        importMessage = nil
        automaticTitle = nil; automaticURL = nil; automaticAction = nil; automaticDate = nil
    }

    func save(to session: AppSession) async -> Bool {
        guard canSave else { return false }
        isSaving = true
        defer { isSaving = false }
        do {
            let url = urlText.trimmingCharacters(in: .whitespacesAndNewlines)
            if !url.isEmpty && URLValidator.webURL(url) == nil { throw AppError.invalidURL }
            let item = InboxItem(title: title, note: note, sourceType: url.isEmpty ? source : (asset == nil ? .url : source),
                                 actionType: action, dueDate: hasDate ? dueDate : nil)
            item.sourceURL = url.isEmpty ? nil : url
            item.localAssetPath = asset?.path
            item.thumbnailPath = asset?.thumbnailPath
            item.rawOCRText = rawOCRText
            item.confidence = confidence
            item.reminderMode = reminderMode
            item.tags = tagsText.split(whereSeparator: { $0 == "," || $0 == "、" || $0 == "#" })
                .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }.filter { !$0.isEmpty }
            item.extractedPrice = extracted.price
            item.extractedPlace = extracted.place
            item.extractedProductName = extracted.productName
            item.extractedAddress = extracted.address
            item.extractedPhone = extracted.phone
            item.extractedEmail = extracted.email
            item.extractedOrderNumber = extracted.orderNumber
            item.extractedReservationNumber = extracted.reservationNumber
            item.extractedReturnDeadline = extracted.returnDeadline
            try session.repository.insert(item)
            saved = true
            if hasDate { await session.requestNotifications() }
            session.refreshSideEffects()
            return true
        } catch { errorMessage = error.localizedDescription; return false }
    }
    func discardUnsavedAsset() {
        if !saved, let asset { AssetStore.remove(asset); self.asset = nil }
    }
}
