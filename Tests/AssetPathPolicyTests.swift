import XCTest
@testable import AtodeYaruBox

final class AssetPathPolicyTests: XCTestCase {
    func testAssetStaysInsideSelectedRoot() {
        let root = URL(fileURLWithPath: "/private/test-box", isDirectory: true)
        XCTAssertEqual(AssetPathPolicy.url(for: "Assets/image.jpg", in: root)?.path,
                       "/private/test-box/Assets/image.jpg")
    }
    func testRejectsTraversalAbsoluteAndEmptyPathComponents() {
        let root = URL(fileURLWithPath: "/private/test-box", isDirectory: true)
        for path in ["/Assets/a.jpg", "Assets/../a.jpg", "Assets\\a.jpg", "Assets//a.jpg",
                     "Assets/a/b.jpg", "Assets/", "Documents/a.jpg", "Assets/a\0.jpg"] {
            XCTAssertNil(AssetPathPolicy.url(for: path, in: root), path)
        }
        XCTAssertNil(AssetPathPolicy.url(for: nil, in: root))
    }
}
