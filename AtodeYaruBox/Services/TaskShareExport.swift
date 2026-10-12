import Foundation
import CoreTransferable
import UniformTypeIdentifiers

struct TaskShareExport: Transferable, Sendable {
    let document: SharedTaskDocument
    static var transferRepresentation: some TransferRepresentation {
        FileRepresentation(exportedContentType: .atodeTask) { value in
            SentTransferredFile(try value.makeFile())
        }
    }
    func makeFile() throws -> URL {
            let directory = FileManager.default.temporaryDirectory.appendingPathComponent("TaskShares", isDirectory: true)
            try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
            // Only remove this app's stale, regular exports from its private temporary folder.
            let keys: Set<URLResourceKey> = [.isRegularFileKey, .isSymbolicLinkKey, .creationDateKey]
            for url in (try? FileManager.default.contentsOfDirectory(at: directory, includingPropertiesForKeys: Array(keys))) ?? [] {
                if let values = try? url.resourceValues(forKeys: keys), values.isRegularFile == true,
                   values.isSymbolicLink != true, url.pathExtension == "atodebox",
                   let created = values.creationDate, created < Date().addingTimeInterval(-86400) {
                    try? FileManager.default.removeItem(at: url)
                }
            }
            let url = directory.appendingPathComponent("あとでやる箱-\(UUID().uuidString).atodebox")
            try SharedTaskCodec.encode(document).write(to: url, options: [.atomic, .completeFileProtection])
            return url
    }
}
