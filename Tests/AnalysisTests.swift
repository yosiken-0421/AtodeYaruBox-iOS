import XCTest
@testable import AtodeYaruBox

final class AnalysisTests: XCTestCase {
    func testJapaneseAndEnglishClassification() {
        let cases: [(String, ActionType)] = [("返品期限 10月10日", .returnItem), ("支払い期限", .payment),
            ("予約番号 AB-123", .reservation), ("返信してください", .reply), ("会議を開催", .event),
            ("買い物に行く", .buy), ("Read this ARTICLE", .read), ("動画を見る", .watch), ("忘れない", .reminder)]
        for (text, expected) in cases { XCTAssertEqual(ClassificationService.classify(text).action, expected, text) }
    }
    func testNoInventedClassificationAndEnglishWordBoundaries() {
        XCTAssertEqual(ClassificationService.classify("かきくけこ").action, .memo)
        XCTAssertEqual(ClassificationService.classify("already thread").action, .memo)
        XCTAssertTrue(ClassificationService.classify("").evidence.isEmpty)
    }
    func testLargeSharedTextDoesNotRunUnboundedClassification() {
        let original = String(repeating: "あ", count: 100_001) + " invoice"
        let result = ClassificationService.classify(original)
        XCTAssertEqual(result.action, .memo)
        XCTAssertTrue(result.evidence.isEmpty)
        XCTAssertTrue(original.hasSuffix("invoice"))
        XCTAssertEqual(ClassificationService.classify("Read article " + original).action, .read)
    }
    func testExtractsOnlyPresentFields() {
        let fields = OCRParser.parse("店名：青空書店\n商品名：ノート\n金額 ¥1,250\n注文番号: ABC-123\n予約番号: RSV-456\nメール a@example.com\nhttps://example.com/item")
        XCTAssertEqual(fields.place, "青空書店")
        XCTAssertEqual(fields.productName, "ノート")
        XCTAssertEqual(fields.price, "¥1,250")
        XCTAssertEqual(fields.orderNumber, "ABC-123")
        XCTAssertEqual(fields.reservationNumber, "RSV-456")
        XCTAssertEqual(fields.email, "a@example.com")
        XCTAssertEqual(fields.url, "https://example.com/item")
        XCTAssertNil(fields.phone)
        XCTAssertNil(fields.returnDeadline)
    }
    func testExplicitJapaneseDateAndReturnDeadline() {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = TimeZone(identifier: "Asia/Tokyo")!
        let fields = OCRParser.parse("開催 2026年10月9日 14時30分\n返品期限：2026年10月20日", calendar: calendar)
        let date = calendar.dateComponents([.year, .month, .day, .hour, .minute], from: fields.date!)
        XCTAssertEqual(date.year, 2026); XCTAssertEqual(date.month, 10); XCTAssertEqual(date.day, 9)
        XCTAssertEqual(date.hour, 14); XCTAssertEqual(date.minute, 30)
        XCTAssertEqual(calendar.component(.day, from: fields.returnDeadline!), 20)
    }
    func testInvalidDatesAndUnknownTextDoNotCreateDates() {
        for text in ["2026/02/30", "2026/13/01", "2026/10/06 25:30", "日付未定", "電話 03-1234-5678"] {
            XCTAssertNil(OCRParser.parse(text).date, text)
        }
        XCTAssertNil(OCRParser.parse("").url)
        XCTAssertNil(OCRParser.parse("曖昧な店の写真").place)
    }
    func testURLValidationRejectsDangerousAndMalformedInputs() {
        for value in ["javascript:alert(1)", "file:///private/data", "https://", "https://user:pass@example.com", "invalid"] {
            XCTAssertNil(URLValidator.webURL(value), value)
        }
        XCTAssertNotNil(URLValidator.webURL(" https://example.com/こんにちは "))
    }
    @MainActor func testSearchIncludesOCRProductAndOrderNumbersWithAllTerms() {
        let item = InboxItem(title: "本", note: "返す")
        item.rawOCRText = "ＨＥＬＬＯ 返品"
        item.extractedProductName = "日本語辞典"
        item.extractedOrderNumber = "ABC-123"
        item.extractedReservationNumber = "RSV-789"
        item.extractedAddress = "東京都渋谷区"
        XCTAssertTrue(SearchEngine.matches(item, query: "hello ABC-123", filter: .all))
        for query in ["日本語辞典", "RSV-789", "東京都渋谷区", "返す"] {
            XCTAssertTrue(SearchEngine.matches(item, query: query, filter: .all))
        }
        XCTAssertFalse(SearchEngine.matches(item, query: "hello 存在しない", filter: .all))
    }
    @MainActor func testSearchFiltersCompletedAndDeadline() {
        let item = InboxItem(title: "支払う", actionType: .payment, dueDate: Date())
        XCTAssertTrue(SearchEngine.matches(item, query: "", filter: .payment))
        XCTAssertFalse(SearchEngine.matches(item, query: "", filter: .buy))
        XCTAssertTrue(SearchEngine.matches(item, query: "", filter: .hasDeadline))
        item.complete()
        XCTAssertTrue(SearchEngine.matches(item, query: "", filter: .completed))
        XCTAssertFalse(SearchEngine.matches(item, query: "", filter: .open))
        item.status = .archived
        XCTAssertFalse(SearchEngine.matches(item, query: "", filter: .all))
    }
}
