import Foundation
import SwiftData

struct LocalMigrationResult: Codable, Equatable {
    var importedItems: Int
    var missingAssets: Int
}

@MainActor
enum LocalStoreMigration {
    static let markerName = "LocalMigration-v1.json"

    static func migrateIfNeeded(from source: URL, to destination: URL,
                                container: ModelContainer) throws -> LocalMigrationResult? {
        let manager = FileManager.default
        let marker = destination.appendingPathComponent(markerName)
        let sourceStore = source.appendingPathComponent("Inbox.store")
        guard source.standardizedFileURL != destination.standardizedFileURL,
              !manager.fileExists(atPath: marker.path),
              manager.fileExists(atPath: sourceStore.path) else { return nil }
        let schema = Schema([InboxItem.self])
        let configuration = ModelConfiguration("LegacyLocal", schema: schema, url: sourceStore,
                                               allowsSave: false, cloudKitDatabase: .none)
        let legacy = try ModelContainer(for: schema, configurations: [configuration])
        let sourceContext = ModelContext(legacy)
        sourceContext.autosaveEnabled = false
        let target = ModelContext(container)
        target.autosaveEnabled = false
        let original = try sourceContext.fetch(FetchDescriptor<InboxItem>(
            sortBy: [SortDescriptor(\InboxItem.updatedAt, order: .reverse)]))
        var identifiers = Set(try target.fetch(FetchDescriptor<InboxItem>()).map(\.id))
        var paths: [String: String] = [:]
        var createdFiles: [URL] = []
        var result = LocalMigrationResult(importedItems: 0, missingAssets: 0)
        var committed = false

        func copyAsset(_ path: String?) throws -> String? {
            guard let path else { return nil }
            if let copied = paths[path] { return copied }
            guard let oldURL = AssetPathPolicy.url(for: path, in: source) else { throw AppError.invalidFile }
            let suffix = oldURL.pathExtension
            let newPath = "Assets/" + UUID().uuidString + (suffix.isEmpty ? "" : "." + suffix)
            guard let newURL = AssetPathPolicy.url(for: newPath, in: destination) else { throw AppError.invalidFile }
            paths[path] = newPath
            guard manager.fileExists(atPath: oldURL.path) else {
                // Keep a missing-file placeholder that cannot point to another item.
                result.missingAssets += 1
                return newPath
            }
            let values = try oldURL.resourceValues(forKeys: [.isRegularFileKey, .isSymbolicLinkKey, .fileSizeKey])
            guard values.isRegularFile == true, values.isSymbolicLink != true else { throw AppError.invalidFile }
            guard (values.fileSize ?? AssetStore.maximumBytes + 1) <= AssetStore.maximumBytes else { throw AppError.fileTooLarge }
            let bytes = try BoundedFileReader.read(oldURL, maximumBytes: AssetStore.maximumBytes)
            guard bytes.count <= AssetStore.maximumBytes else { throw AppError.fileTooLarge }
            try manager.createDirectory(at: newURL.deletingLastPathComponent(), withIntermediateDirectories: true,
                attributes: [.protectionKey: FileProtectionType.completeUntilFirstUserAuthentication])
            try bytes.write(to: newURL, options: [.atomic, .completeFileProtectionUntilFirstUserAuthentication])
            createdFiles.append(newURL)
            return newPath
        }

        do {
            for sourceItem in original where !identifiers.contains(sourceItem.id) {
                let item = InboxItem(title: sourceItem.title)
                item.id = sourceItem.id
                item.copyPersistedState(from: sourceItem)
                item.localAssetPath = try copyAsset(sourceItem.localAssetPath)
                item.thumbnailPath = try copyAsset(sourceItem.thumbnailPath)
                target.insert(item)
                identifiers.insert(item.id)
                result.importedItems += 1
            }
            try target.save()
            committed = true
            // A failed marker write is retryable: existing IDs always take precedence.
            try JSONEncoder().encode(result).write(to: marker,
                options: [.atomic, .completeFileProtectionUntilFirstUserAuthentication])
            return result
        } catch {
            if !committed {
                target.rollback()
                for file in createdFiles { try? manager.removeItem(at: file) }
            }
            // Source DB and source files are never changed or deleted by migration.
            throw error
        }
    }
}
