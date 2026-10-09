import XCTest
@testable import AtodeYaruBox

final class BoundedFileReaderTests: XCTestCase {
    private func directory() throws -> URL {
        let url = FileManager.default.temporaryDirectory.appendingPathComponent("BoundedQA-" + UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: url, withIntermediateDirectories: true)
        addTeardownBlock { try FileManager.default.removeItem(at: url) }
        return url
    }

    func testReadsExactLimitAndEmptyFileWithoutChangingOriginal() throws {
        let directory = try directory()
        let file = directory.appendingPathComponent("fixture.bin")
        let original = Data((0..<150000).map { UInt8($0 % 251) })
        try original.write(to: file)
        XCTAssertEqual(try BoundedFileReader.read(file, maximumBytes: original.count), original)
        XCTAssertEqual(try Data(contentsOf: file), original)
        let empty = directory.appendingPathComponent("empty.bin")
        try Data().write(to: empty)
        XCTAssertEqual(try BoundedFileReader.read(empty, maximumBytes: 0), Data())
    }

    func testRejectsOversizedDirectoryMissingFileAndInvalidLimit() throws {
        let directory = try directory()
        let file = directory.appendingPathComponent("oversized.bin")
        try Data(repeating: 7, count: 65537).write(to: file)
        XCTAssertThrowsError(try BoundedFileReader.read(file, maximumBytes: 65536)) { error in
            if let kind = error as? AppError, case .fileTooLarge = kind { return }
            XCTFail("Oversized input must report fileTooLarge")
        }
        XCTAssertThrowsError(try BoundedFileReader.read(directory, maximumBytes: 65536))
        XCTAssertThrowsError(try BoundedFileReader.read(directory.appendingPathComponent("missing.bin"), maximumBytes: 65536))
        XCTAssertThrowsError(try BoundedFileReader.read(file, maximumBytes: -1))
        XCTAssertThrowsError(try BoundedFileReader.read(URL(string: "https://example.invalid/file")!, maximumBytes: 65536))
        XCTAssertEqual(try Data(contentsOf: file).count, 65537)
    }
}
