import XCTest
import UIKit
import SwiftData
import UniformTypeIdentifiers
@testable import AtodeYaruBox

/// Actual NSItemProvider callbacks, classification and SwiftData; no browser/network access.
final class ShareProviderTests: XCTestCase {
    @MainActor private func imageBytes() throws -> Data {
        let format = UIGraphicsImageRendererFormat()
        format.scale = 1
        format.opaque = true
        let image = UIGraphicsImageRenderer(size: CGSize(width: 1500, height: 600), format: format).image { context in
            UIColor.white.setFill()
            context.fill(CGRect(x: 0, y: 0, width: 1500, height: 600))
            ("返品期限: 2030/10/08 19:00\nOrder number: SHARE123" as NSString).draw(
                in: CGRect(x: 60, y: 60, width: 1380, height: 480),
                withAttributes: [.font: UIFont.systemFont(ofSize: 56), .foregroundColor: UIColor.black])
        }
        return try XCTUnwrap(image.pngData())
    }

    @MainActor private func assertStoredAttachment(_ draft: ShareDraft, original: Data, source: SourceType) throws {
        let item = try ShareImportService.item(from: draft)
        let store = try SharedStore.container(inMemory: true)
        try InboxRepository(context: store.mainContext).insert(item)
        let persisted = try XCTUnwrap(InboxRepository(context: ModelContext(store)).find(item.id))
        let url = try XCTUnwrap(AssetStore.url(for: persisted.localAssetPath))
        XCTAssertEqual(try Data(contentsOf: url), original)
        XCTAssertEqual(persisted.sourceType, source)
        XCTAssertEqual(persisted.status, .inbox)
        XCTAssertNil(persisted.dueDate)
    }

    @MainActor func testURLProviderPersistsAsReviewedInboxWithoutDate() async throws {
        let original = "https://example.com/atode-share-test"
        let url = try XCTUnwrap(URL(string: original))
        let draft = try await ShareImportService.read(NSItemProvider(object: url as NSURL))
        XCTAssertEqual(draft.source, .url)
        XCTAssertEqual(draft.url, original)
        let item = try ShareImportService.item(from: draft)
        XCTAssertEqual(item.status, .inbox)
        XCTAssertNil(item.dueDate)
        XCTAssertEqual(item.actionType, .read)
        let container = try SharedStore.container(inMemory: true)
        let repository = InboxRepository(context: container.mainContext)
        try repository.insert(item)
        let persisted = try XCTUnwrap(InboxRepository(context: ModelContext(container)).find(item.id))
        XCTAssertEqual(persisted.sourceURL, original)
        XCTAssertTrue(SearchEngine.matches(persisted, query: "atode-share-test", filter: .all))
    }

    @MainActor func testTextProviderPreservesOriginalAndRequiresDateReview() async throws {
        let text = "予約番号: BOOK123\n2030/10/0908:00"
        let draft = try await ShareImportService.read(NSItemProvider(object: text as NSString))
        XCTAssertEqual(draft.rawText, text)
        XCTAssertEqual(draft.note, text)
        XCTAssertEqual(draft.action, .reservation)
        let expected = Calendar.current.date(from: DateComponents(year: 2030, month: 10, day: 9, hour: 8))
        XCTAssertEqual(draft.fields.date, expected)
        let item = try ShareImportService.item(from: draft)
        XCTAssertEqual(item.status, .inbox)
        XCTAssertNil(item.dueDate, "Shared date candidates must be reviewed before notification scheduling")
        XCTAssertEqual(item.rawOCRText, text)
        XCTAssertEqual(item.extractedReservationNumber, "BOOK123")
    }

    @MainActor func testDangerousSharedURLIsRejected() async throws {
        let url = try XCTUnwrap(URL(string: "javascript:alert(1)"))
        do {
            _ = try await ShareImportService.read(NSItemProvider(object: url as NSURL))
            XCTFail("A script URL must never be saved or opened")
        } catch AppError.invalidURL {
            // The actual provider completed, and the URL validation rejected its value.
        }
    }

    @MainActor func testImageProviderRecognizesAndPersistsOriginalForReview() async throws {
        let bytes = try imageBytes()
        let provider = NSItemProvider()
        provider.suggestedName = "共有画像の検証"
        provider.registerDataRepresentation(forTypeIdentifier: UTType.png.identifier, visibility: .all) { completion in
            completion(bytes, nil)
            return nil
        }
        let draft = try await ShareImportService.read(provider)
        let asset = try XCTUnwrap(draft.asset)
        defer { AssetStore.remove(asset) }
        XCTAssertEqual(draft.action, .returnItem, draft.rawText)
        XCTAssertEqual(draft.fields.orderNumber, "SHARE123", draft.rawText)
        XCTAssertNotNil(draft.fields.returnDeadline)
        XCTAssertNotNil(asset.thumbnailPath)
        try assertStoredAttachment(draft, original: bytes, source: .photo)
    }

    @MainActor func testPDFProviderUsesVisionAndPreservesOriginalForReview() async throws {
        let image = try XCTUnwrap(UIImage(data: imageBytes()))
        let bounds = CGRect(x: 0, y: 0, width: 1500, height: 600)
        let pdf = UIGraphicsPDFRenderer(bounds: bounds).pdfData { context in
            context.beginPage()
            image.draw(in: bounds)
        }
        let provider = NSItemProvider()
        provider.suggestedName = "共有PDFの検証"
        provider.registerDataRepresentation(forTypeIdentifier: UTType.pdf.identifier, visibility: .all) { completion in
            completion(pdf, nil)
            return nil
        }
        let draft = try await ShareImportService.read(provider)
        let asset = try XCTUnwrap(draft.asset)
        defer { AssetStore.remove(asset) }
        XCTAssertEqual(draft.action, .returnItem, draft.rawText)
        XCTAssertEqual(draft.fields.orderNumber, "SHARE123", draft.rawText)
        XCTAssertNotNil(draft.fields.returnDeadline)
        try assertStoredAttachment(draft, original: pdf, source: .pdf)
    }

    @MainActor func testFileRepresentationCopiesOriginalIntoSharedStorage() async throws {
        let bytes = Data([0x00, 0xFF, 0x10, 0x42, 0x7F])
        let original = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString + ".bin")
        try bytes.write(to: original, options: .atomic)
        defer { try? FileManager.default.removeItem(at: original) }
        let provider = NSItemProvider()
        provider.suggestedName = "共有ファイルの検証"
        provider.registerFileRepresentation(forTypeIdentifier: UTType.data.identifier, fileOptions: [], visibility: .all) { completion in
            completion(original, false, nil)
            return nil
        }
        let draft = try await ShareImportService.read(provider)
        let asset = try XCTUnwrap(draft.asset)
        defer { AssetStore.remove(asset) }
        // The result must remain usable after the provider's original disappears.
        try FileManager.default.removeItem(at: original)
        XCTAssertEqual(draft.source, .file)
        XCTAssertTrue(draft.rawText.isEmpty)
        try assertStoredAttachment(draft, original: bytes, source: .file)
    }
}
