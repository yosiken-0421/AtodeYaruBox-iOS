import XCTest
import UniformTypeIdentifiers
@testable import AtodeYaruBox

final class AssetStoreTests: XCTestCase {
    func testTraversalAndEmptyAssetsAreRejected() {
        for path in ["../Inbox.store", "/etc/passwd", "Assets/../../file", "Assets\\file", "file"] {
            XCTAssertNil(AssetStore.url(for: path))
        }
        XCTAssertThrowsError(try AssetStore.save(Data(), type: .data))
    }
    func testOversizedAssetIsRejectedBeforeWriting() {
        XCTAssertThrowsError(try AssetStore.save(Data(count: AssetStore.maximumBytes + 1), type: .data))
    }
    func testOriginalFileRoundTripAndCleanup() throws {
        let bytes = Data("日本語のメモ".utf8)
        let asset = try AssetStore.save(bytes, type: .plainText)
        defer { AssetStore.remove(asset) }
        let url = try XCTUnwrap(AssetStore.url(for: asset.path))
        XCTAssertEqual(try Data(contentsOf: url), bytes)
    }
}
