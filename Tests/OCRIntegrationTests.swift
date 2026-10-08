import XCTest
import UIKit
import SwiftData
import UniformTypeIdentifiers
@testable import AtodeYaruBox

/// Real Vision recognition and SwiftData persistence; no cloud or photo library access.
final class OCRIntegrationTests: XCTestCase {
    @MainActor private func imageText(_ text: String) throws -> Data {
        let format = UIGraphicsImageRendererFormat()
        format.scale = 1
        format.opaque = true
        let image = UIGraphicsImageRenderer(size: CGSize(width: 1500, height: 600), format: format).image { context in
            UIColor.white.setFill()
            context.fill(CGRect(x: 0, y: 0, width: 1500, height: 600))
            (text as NSString).draw(in: CGRect(x: 60, y: 60, width: 1380, height: 480),
                withAttributes: [.font: UIFont.systemFont(ofSize: 56), .foregroundColor: UIColor.black])
        }
        return try XCTUnwrap(image.pngData())
    }

    @MainActor func testImageRecognitionClassificationAndSave() async throws {
        let bytes = try imageText("返品期限: 2030/10/08 19:00\nOrder number: AB12345")
        let model = ComposeViewModel()
        defer { model.discardUnsavedAsset() }
        await model.importData(bytes, type: .png, source: .photo)
        XCTAssertTrue(model.rawOCRText.contains("返品期限"), model.rawOCRText)
        XCTAssertEqual(model.action, .returnItem, model.rawOCRText)
        XCTAssertEqual(model.extracted.orderNumber, "AB12345", model.rawOCRText)
        XCTAssertNotNil(model.extracted.returnDeadline, model.rawOCRText)
        XCTAssertTrue(model.hasDate, model.rawOCRText)
        let asset = try XCTUnwrap(model.asset)
        defer { AssetStore.remove(asset) }
        XCTAssertNotNil(asset.thumbnailPath)
        let container = try SharedStore.container(inMemory: true)
        let session = AppSession(container: container, externalEffectsEnabled: false)
        let saved = await model.save(to: session)
        XCTAssertTrue(saved, model.errorMessage ?? "")
        let repository = InboxRepository(context: ModelContext(container))
        let item = try XCTUnwrap(repository.all().first)
        XCTAssertEqual(item.sourceType, .photo)
        XCTAssertEqual(item.actionType, .returnItem)
        XCTAssertEqual(item.extractedOrderNumber, "AB12345")
        XCTAssertEqual(item.dueDate, model.extracted.returnDeadline)
        XCTAssertEqual(item.rawOCRText, model.rawOCRText)
        XCTAssertEqual(item.localAssetPath, asset.path)
        XCTAssertTrue(SearchEngine.matches(item, query: "AB12345", filter: .all))
    }

    @MainActor func testScannedPDFUsesVisionAndPreservesOriginalFile() async throws {
        let image = try XCTUnwrap(UIImage(data: imageText("Reservation number: BOOK123\n2030/10/09 08:00")))
        let bounds = CGRect(x: 0, y: 0, width: 1500, height: 600)
        let pdf = UIGraphicsPDFRenderer(bounds: bounds).pdfData { context in
            context.beginPage()
            image.draw(in: bounds)
        }
        let model = ComposeViewModel()
        defer { model.discardUnsavedAsset() }
        await model.importData(pdf, type: .pdf, source: .pdf)
        XCTAssertEqual(model.action, .reservation, model.rawOCRText)
        XCTAssertEqual(model.extracted.reservationNumber, "BOOK123", model.rawOCRText)
        XCTAssertTrue(model.hasDate, model.rawOCRText)
        let expected = Calendar.current.date(from: DateComponents(year: 2030, month: 10, day: 9, hour: 8, minute: 0))
        XCTAssertEqual(model.extracted.date, expected, model.rawOCRText)
        XCTAssertEqual(model.dueDate, expected, model.rawOCRText)
        let url = try XCTUnwrap(AssetStore.url(for: model.asset?.path))
        XCTAssertEqual(try Data(contentsOf: url), pdf)
        XCTAssertTrue(model.canSave)
    }

    @MainActor func testFailedImageRecognitionStillSavesOriginalAttachment() async throws {
        let bytes = Data("Unrecognizable image bytes".utf8)
        let model = ComposeViewModel()
        defer { model.discardUnsavedAsset() }
        await model.importData(bytes, type: .png, source: .photo)
        XCTAssertTrue(model.rawOCRText.isEmpty)
        XCTAssertNotNil(model.importMessage)
        let asset = try XCTUnwrap(model.asset)
        defer { AssetStore.remove(asset) }
        let session = AppSession(container: try SharedStore.container(inMemory: true), externalEffectsEnabled: false)
        let saved = await model.save(to: session)
        XCTAssertTrue(saved)
        let item = try XCTUnwrap(session.repository.all().first)
        let url = try XCTUnwrap(AssetStore.url(for: item.localAssetPath))
        XCTAssertEqual(try Data(contentsOf: url), bytes)
        XCTAssertEqual(item.title, "写真から保存")
        XCTAssertEqual(item.sourceType, .photo)
        XCTAssertNil(item.dueDate)
    }
}
