import XCTest
import UniformTypeIdentifiers
@testable import AtodeYaruBox

final class ComposeImportTests: XCTestCase {
    @MainActor func testReplacementClearsOriginalTextAndExtractedIdentifiers() async {
        let model = ComposeViewModel()
        defer { model.discardUnsavedAsset() }
        await model.importData(Data("注文番号: ORDER-123\n2030/01/01 18:00\nhttps://example.com/order".utf8), type: .plainText, source: .file)
        XCTAssertFalse(model.rawOCRText.isEmpty)
        XCTAssertNotNil(model.extracted.orderNumber)
        XCTAssertEqual(model.urlText, "https://example.com/order")
        XCTAssertTrue(model.hasDate)

        await model.importData(Data([1, 2, 3]), type: .data, source: .file)
        XCTAssertTrue(model.rawOCRText.isEmpty)
        XCTAssertNil(model.extracted.orderNumber)
        XCTAssertTrue(model.urlText.isEmpty)
        XCTAssertFalse(model.hasDate)
        XCTAssertEqual(model.title, "ファイルから保存")
        XCTAssertTrue(model.canSave)
    }

    @MainActor func testFailedOCRDoesNotReusePreviousAnalysis() async {
        let model = ComposeViewModel()
        defer { model.discardUnsavedAsset() }
        await model.importData(Data("予約番号: BOOK-123".utf8), type: .plainText, source: .file)
        XCTAssertNotNil(model.extracted.reservationNumber)

        await model.importData(Data("This is not a PNG image".utf8), type: .png, source: .photo)
        XCTAssertNotNil(model.asset)
        XCTAssertTrue(model.rawOCRText.isEmpty)
        XCTAssertNil(model.extracted.reservationNumber)
        XCTAssertNotNil(model.importMessage)
        XCTAssertEqual(model.title, "写真から保存")
        XCTAssertTrue(model.canSave)
    }

    @MainActor func testReplacementPreservesManuallyEditedTitleURLAndDate() async {
        let model = ComposeViewModel()
        defer { model.discardUnsavedAsset() }
        await model.importData(Data("予約番号: BOOK-123\n2030/01/01 18:00\nhttps://example.com/old".utf8), type: .plainText, source: .file)
        model.title = "自分で決めたタイトル"
        model.urlText = "https://example.com/manual"
        model.note = "自分のメモ"
        model.action = .read
        let date = Date(timeIntervalSince1970: 1_900_000_000)
        model.dueDate = date; model.hasDate = true

        await model.importData(Data([1]), type: .data, source: .file)
        XCTAssertEqual(model.title, "自分で決めたタイトル")
        XCTAssertEqual(model.urlText, "https://example.com/manual")
        XCTAssertEqual(model.note, "自分のメモ")
        XCTAssertEqual(model.action, .read)
        XCTAssertTrue(model.hasDate)
        XCTAssertEqual(model.dueDate, date)
        XCTAssertNil(model.extracted.reservationNumber)
    }

    @MainActor func testRejectedReplacementKeepsPreviousAttachment() async {
        let model = ComposeViewModel()
        defer { model.discardUnsavedAsset() }
        await model.importData(Data("元のメモ".utf8), type: .plainText, source: .file)
        let path = model.asset?.path
        await model.importData(Data(), type: .data, source: .file)
        XCTAssertEqual(model.asset?.path, path)
        XCTAssertEqual(model.rawOCRText, "元のメモ")
        XCTAssertNotNil(model.errorMessage)
        XCTAssertTrue(model.canSave)
    }
}
