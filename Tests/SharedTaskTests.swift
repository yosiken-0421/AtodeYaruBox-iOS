import XCTest
import SwiftData
import UniformTypeIdentifiers
import UIKit
@testable import AtodeYaruBox

final class SharedTaskTests: XCTestCase {
    private func document() -> SharedTaskDocument {
        SharedTaskDocument(title: "買い物をお願い", note: "牛乳を1本", action: .buy,
                           dueDate: Date(timeIntervalSince1970: 1900000000), sourceURL: "https://example.com/shop")
    }
    func testDocumentRoundTripKeepsSelectedFieldsAndGeneratesNewIdentity() throws {
        let original = document(); let result = try SharedTaskCodec.decode(SharedTaskCodec.encode(original))
        XCTAssertEqual(result.title, original.title); XCTAssertEqual(result.note, original.note)
        XCTAssertEqual(result.dueDate, original.dueDate); XCTAssertEqual(result.action, .buy)
        XCTAssertNotEqual(original.id, result.id)
    }
    func testExportDoesNotContainPersistenceIDsOrPrivateAssetMetadata() throws {
        let value = document(); let text = String(decoding: try SharedTaskCodec.encode(value), as: UTF8.self)
        for key in [value.id.uuidString, "localAssetPath", "rawOCRText", "locationReminder", "status", "completedAt", "extractedOrderNumber"] {
            XCTAssertFalse(text.contains(key))
        }
    }
    func testUnknownVersionsMalformedJSONAndOversizedDataAreRejected() {
        var value = document(); value.version = 2; XCTAssertThrowsError(try SharedTaskCodec.encode(value))
        XCTAssertThrowsError(try SharedTaskCodec.decode(Data("not JSON".utf8)))
        XCTAssertThrowsError(try SharedTaskCodec.decode(Data(repeating: 0, count: SharedTaskCodec.maximumBytes + 1)))
    }
    func testUnsafeURLsEmptyTitlesOversizedNotesAndExtremeDatesAreRejected() {
        var value = document(); value.sourceURL = "javascript:alert(1)"; XCTAssertThrowsError(try SharedTaskCodec.encode(value))
        value = document(); value.sourceURL = "https://user:password@example.com"; XCTAssertThrowsError(try SharedTaskCodec.encode(value))
        value = document(); value.title = " \n "; XCTAssertThrowsError(try SharedTaskCodec.encode(value))
        value = document(); value.note = String(repeating: "字", count: 12000); XCTAssertThrowsError(try SharedTaskCodec.encode(value))
        value = document(); value.dueDate = .distantFuture; XCTAssertThrowsError(try SharedTaskCodec.encode(value))
    }
    func testMessageReflectsOnlySelectedFields() {
        let value = SharedTaskDocument(title: "共有するタイトル", note: "", action: .memo, dueDate: nil, sourceURL: nil)
        XCTAssertEqual(SharedTaskCodec.text(value), "共有するタイトル\n種類：メモ")
    }
    @MainActor func testShareExtensionDraftCreatesIndependentReviewItem() throws {
        let draft = try ShareImportService.sharedDraft(SharedTaskCodec.encode(document()))
        let item = try ShareImportService.item(from: draft)
        XCTAssertEqual(item.status, .inbox); XCTAssertEqual(item.actionType, .buy)
        XCTAssertEqual(item.dueDate, document().dueDate); XCTAssertNil(item.localAssetPath)
        XCTAssertNil(item.locationReminder); XCTAssertTrue(item.rawOCRText.isEmpty)
    }
    @MainActor func testComposeImportSavesCopyAndDoesNotMutateOriginal() async throws {
        let session = AppSession(container: try SharedStore.container(inMemory: true), externalEffectsEnabled: false)
        let original = InboxItem(title: "元の項目", note: "個人メモ"); try session.repository.insert(original)
        let model = ComposeViewModel(); model.applySharedTask(document())
        let saved = await model.save(to: session); XCTAssertTrue(saved)
        let items = try session.repository.all(); XCTAssertEqual(items.count, 2)
        let copy = try XCTUnwrap(items.first { $0.id != original.id })
        XCTAssertEqual(copy.title, document().title); XCTAssertEqual(copy.dueDate, document().dueDate)
        XCTAssertEqual(original.title, "元の項目"); XCTAssertNil(copy.localAssetPath); XCTAssertNil(copy.locationReminder)
    }
    @MainActor func testMalformedFileImportPreservesExistingDraft() async {
        let model = ComposeViewModel(); model.title = "書きかけのメモ"
        await model.importData(Data("broken".utf8), type: .atodeTask, source: .file)
        XCTAssertEqual(model.title, "書きかけのメモ"); XCTAssertNotNil(model.errorMessage); XCTAssertNil(model.asset)
    }
    func testExportWritesValidDocumentInPrivateTemporaryFolder() throws {
        let url = try TaskShareExport(document: document()).makeFile()
        defer { try? FileManager.default.removeItem(at: url) }
        XCTAssertEqual(url.pathExtension, "atodebox")
        XCTAssertTrue(url.path.contains("TaskShares"))
        XCTAssertEqual(try SharedTaskCodec.decode(Data(contentsOf: url)).title, document().title)
    }
    @MainActor func testActualFileProviderRoundTripPreservesSharedDateWithoutAsset() async throws {
        let url = try TaskShareExport(document: document()).makeFile()
        defer { try? FileManager.default.removeItem(at: url) }
        let provider = NSItemProvider()
        provider.registerFileRepresentation(forTypeIdentifier: UTType.atodeTask.identifier, fileOptions: [], visibility: .all) { completion in
            completion(url, false, nil); return nil
        }
        let draft = try await ShareImportService.read(provider)
        XCTAssertEqual(draft.title, document().title); XCTAssertEqual(draft.sharedDueDate, document().dueDate)
        XCTAssertNil(draft.asset); XCTAssertTrue(draft.rawText.isEmpty)
    }
}
