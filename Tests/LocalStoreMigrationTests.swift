import XCTest
import SwiftData
@testable import AtodeYaruBox

final class LocalStoreMigrationTests: XCTestCase {
    @MainActor private func store(at directory: URL) throws -> ModelContainer {
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        let schema = Schema([InboxItem.self])
        return try ModelContainer(for: schema, configurations: [ModelConfiguration(
            schema: schema, url: directory.appendingPathComponent("Inbox.store"), cloudKitDatabase: .none)])
    }
    private func fixture() -> (URL, URL, URL) {
        let base = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString, isDirectory: true)
        return (base, base.appendingPathComponent("Local"), base.appendingPathComponent("Group"))
    }
    @MainActor func testCopiesRecordsAndAssetsWithoutRemovingSource() throws {
        let (base, local, group) = fixture()
        defer { try? FileManager.default.removeItem(at: base) }
        let old = try store(at: local)
        let target = try store(at: group)
        let item = InboxItem(title: "写真の注文", note: "メモ", actionType: .buy)
        item.rawOCRText = "注文番号 ORDER-123"; item.extractedOrderNumber = "ORDER-123"
        item.tags = ["注文"]; item.localAssetPath = "Assets/original.txt"
        let file = local.appendingPathComponent(item.localAssetPath!)
        try FileManager.default.createDirectory(at: file.deletingLastPathComponent(), withIntermediateDirectories: true)
        try Data("original bytes".utf8).write(to: file)
        old.mainContext.insert(item); try old.mainContext.save()

        let result = try LocalStoreMigration.migrateIfNeeded(from: local, to: group, container: target)
        XCTAssertEqual(result?.importedItems, 1)
        let saved = try XCTUnwrap(InboxRepository(context: ModelContext(target)).find(item.id))
        XCTAssertEqual(saved.note, "メモ"); XCTAssertEqual(saved.tags, ["注文"])
        XCTAssertEqual(saved.rawOCRText, "注文番号 ORDER-123")
        XCTAssertEqual(saved.extractedOrderNumber, "ORDER-123")
        let copied = try XCTUnwrap(AssetPathPolicy.url(for: saved.localAssetPath, in: group))
        XCTAssertEqual(try Data(contentsOf: copied), Data("original bytes".utf8))
        XCTAssertTrue(FileManager.default.fileExists(atPath: file.path))
        XCTAssertEqual(try InboxRepository(context: ModelContext(old)).all().count, 1)
        XCTAssertNil(try LocalStoreMigration.migrateIfNeeded(from: local, to: group, container: target))
    }
    @MainActor func testRetryKeepsGroupEditsAndDoesNotDuplicateIDs() throws {
        let (base, local, group) = fixture()
        defer { try? FileManager.default.removeItem(at: base) }
        let old = try store(at: local)
        let target = try store(at: group)
        let item = InboxItem(title: "元のタイトル")
        old.mainContext.insert(item); try old.mainContext.save()
        let groupItem = InboxItem(title: "グループで編集したタイトル")
        groupItem.id = item.id; groupItem.complete()
        target.mainContext.insert(groupItem); try target.mainContext.save()
        let result = try LocalStoreMigration.migrateIfNeeded(from: local, to: group, container: target)
        XCTAssertEqual(result?.importedItems, 0)
        let values = try InboxRepository(context: ModelContext(target)).all()
        XCTAssertEqual(values.count, 1)
        XCTAssertEqual(values.first?.title, "グループで編集したタイトル")
        XCTAssertEqual(values.first?.status, .completed)
    }
    @MainActor func testMissingFilePreservesRecordAndCannotUseUnrelatedFile() throws {
        let (base, local, group) = fixture()
        defer { try? FileManager.default.removeItem(at: base) }
        let old = try store(at: local)
        let target = try store(at: group)
        let item = InboxItem(title: "元ファイルが欠落", note: "原文は残す")
        item.localAssetPath = "Assets/missing.jpg"
        old.mainContext.insert(item); try old.mainContext.save()
        let conflicting = group.appendingPathComponent("Assets/missing.jpg")
        try FileManager.default.createDirectory(at: conflicting.deletingLastPathComponent(), withIntermediateDirectories: true)
        try Data("unrelated image".utf8).write(to: conflicting)
        let result = try LocalStoreMigration.migrateIfNeeded(from: local, to: group, container: target)
        XCTAssertEqual(result?.missingAssets, 1)
        let saved = try XCTUnwrap(InboxRepository(context: ModelContext(target)).find(item.id))
        XCTAssertEqual(saved.note, "原文は残す")
        XCTAssertNotEqual(saved.localAssetPath, item.localAssetPath)
        let placeholder = try XCTUnwrap(AssetPathPolicy.url(for: saved.localAssetPath, in: group))
        XCTAssertFalse(FileManager.default.fileExists(atPath: placeholder.path))
        XCTAssertEqual(try Data(contentsOf: conflicting), Data("unrelated image".utf8))
    }
    @MainActor func testUnsafeAssetRollsBackAndKeepsLegacyStore() throws {
        let (base, local, group) = fixture()
        defer { try? FileManager.default.removeItem(at: base) }
        let old = try store(at: local)
        let target = try store(at: group)
        let item = InboxItem(title: "不正なパス")
        item.localAssetPath = "../outside.jpg"
        old.mainContext.insert(item); try old.mainContext.save()
        XCTAssertThrowsError(try LocalStoreMigration.migrateIfNeeded(from: local, to: group, container: target))
        XCTAssertTrue(try InboxRepository(context: ModelContext(target)).all().isEmpty)
        XCTAssertEqual(try InboxRepository(context: ModelContext(old)).all().count, 1)
        XCTAssertFalse(FileManager.default.fileExists(atPath: group.appendingPathComponent(LocalStoreMigration.markerName).path))
    }
    @MainActor func testFreshInstallAndSameDirectoryNeedNoMigration() throws {
        let (base, local, group) = fixture()
        defer { try? FileManager.default.removeItem(at: base) }
        let target = try store(at: group)
        XCTAssertNil(try LocalStoreMigration.migrateIfNeeded(from: local, to: group, container: target))
        XCTAssertNil(try LocalStoreMigration.migrateIfNeeded(from: group, to: group, container: target))
    }
}
