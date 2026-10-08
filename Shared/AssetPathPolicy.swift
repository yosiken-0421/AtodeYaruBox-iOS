import Foundation

enum AssetPathPolicy {
    static func url(for path: String?, in root: URL) -> URL? {
        guard let path, !path.hasPrefix("/"), !path.contains("\\"),
              path.split(separator: "/", omittingEmptySubsequences: false).count == 2,
              path.hasPrefix("Assets/"), !path.contains(".."),
              !path.hasSuffix("/"), !path.contains("\0") else { return nil }
        let base = root.standardizedFileURL
        let result = base.appendingPathComponent(path).standardizedFileURL
        guard result.deletingLastPathComponent() == base.appendingPathComponent("Assets", isDirectory: true) else { return nil }
        return result
    }
}
