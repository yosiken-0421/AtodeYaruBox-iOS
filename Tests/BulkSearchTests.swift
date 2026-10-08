import XCTest
import SwiftData
@testable import AtodeYaruBox

final class BulkSearchTests: XCTestCase {
    @MainActor func testThousandStoredItemsSearchFullOCRAndRespectCompletionFilter() throws {
        let container = try SharedStore.container(inMemory: true)
        let context = container.mainContext
        context.autosaveEnabled = false
        let target = InboxItem(title: "QA 完了済みの注文", sourceType: .photo, actionType: .buy)
        // Classification is deliberately bounded, while full-text search must
        // still find a word near the end of the unchanged original OCR text.
        target.rawOCRText = String(repeating: "保存した原文。", count: 20_000) + " \nＢＯＸ－９７３１"
        target.extractedOrderNumber = "ORDER-9731"
        target.complete()
        context.insert(target)
        for index in 0..<999 {
            let item = InboxItem(title: "QA メモ \(index)", note: "日本語の確認内容 \(index)")
            item.rawOCRText = String(repeating: "箱に残す内容。", count: 80)
            context.insert(item)
        }
        try context.save()
        let stored = try InboxRepository(context: ModelContext(container)).all()
        XCTAssertEqual(stored.count, 1_000)
        let matches = stored.filter { SearchEngine.matches($0, query: "box-9731 ORDER-9731", filter: .completed) }
        XCTAssertEqual(matches.map(\.id), [target.id])
        XCTAssertFalse(stored.contains { SearchEngine.matches($0, query: "BOX-9731", filter: .open) })
        XCTAssertTrue(matches.first?.rawOCRText.hasSuffix("ＢＯＸ－９７３１") == true)
    }
}
