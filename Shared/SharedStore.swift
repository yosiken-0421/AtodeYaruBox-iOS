import Foundation
import SwiftData

enum SharedStore {
    static var groupID: String {
        Bundle.main.object(forInfoDictionaryKey: "AppGroupIdentifier") as? String ?? "group.jp.atodeyarubox.app"
    }
    static func directory(requireGroup: Bool = false) throws -> URL {
        let fileManager = FileManager.default
        let root: URL
        if let group = fileManager.containerURL(forSecurityApplicationGroupIdentifier: groupID) {
            root = group
        } else {
            guard !requireGroup else { throw AppError.missingAppGroup }
            root = try fileManager.url(for: .applicationSupportDirectory, in: .userDomainMask,
                                       appropriateFor: nil, create: true)
        }
        let directory = root.appendingPathComponent("AtodeYaruBox", isDirectory: true)
        try fileManager.createDirectory(at: directory, withIntermediateDirectories: true,
            attributes: [.protectionKey: FileProtectionType.completeUntilFirstUserAuthentication])
        return directory
    }

    @MainActor
    static func container(inMemory: Bool = false, requireGroup: Bool = false) throws -> ModelContainer {
        let schema = Schema([InboxItem.self])
        let configuration: ModelConfiguration
        if inMemory {
            configuration = ModelConfiguration(schema: schema, isStoredInMemoryOnly: true, cloudKitDatabase: .none)
        } else {
            let url = try directory(requireGroup: requireGroup).appendingPathComponent("Inbox.store")
            // No automatic iCloud discovery. Local data is never silently uploaded.
            configuration = ModelConfiguration(schema: schema, url: url, cloudKitDatabase: .none)
        }
        let container = try ModelContainer(for: schema, configurations: [configuration])
        if !inMemory, !requireGroup,
           FileManager.default.containerURL(forSecurityApplicationGroupIdentifier: groupID) != nil,
           let support = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first {
            let legacy = support.appendingPathComponent("AtodeYaruBox", isDirectory: true)
            _ = try LocalStoreMigration.migrateIfNeeded(from: legacy, to: directory(requireGroup: true), container: container)
        }
        return container
    }
}
