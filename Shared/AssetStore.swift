import Foundation
import UIKit
import UniformTypeIdentifiers
import ImageIO

struct StoredAsset: Sendable {
    var path: String
    var thumbnailPath: String?
}

enum AssetStore {
    static let maximumBytes = 25 * 1024 * 1024

    static func save(_ data: Data, type: UTType, requireGroup: Bool = false) throws -> StoredAsset {
        guard !data.isEmpty else { throw AppError.invalidFile }
        guard data.count <= maximumBytes else { throw AppError.fileTooLarge }
        let directory = try SharedStore.directory(requireGroup: requireGroup).appendingPathComponent("Assets", isDirectory: true)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true,
            attributes: [.protectionKey: FileProtectionType.completeUntilFirstUserAuthentication])
        let suffix = type.preferredFilenameExtension ?? "bin"
        let name = UUID().uuidString + "." + suffix
        let url = directory.appendingPathComponent(name)
        try data.write(to: url, options: [.atomic, .completeFileProtectionUntilFirstUserAuthentication])
        var thumbnail: String?
        if type.conforms(to: .image), let source = CGImageSourceCreateWithData(data as CFData, nil),
           let raster = CGImageSourceCreateThumbnailAtIndex(source, 0, [
            kCGImageSourceCreateThumbnailFromImageAlways: true,
            kCGImageSourceThumbnailMaxPixelSize: 240,
            kCGImageSourceCreateThumbnailWithTransform: true
           ] as CFDictionary) {
            let image = UIImage(cgImage: raster)
            let aspect = min(1, 240 / max(max(image.size.width, image.size.height), 1))
            let size = CGSize(width: max(1, image.size.width * aspect), height: max(1, image.size.height * aspect))
            let format = UIGraphicsImageRendererFormat()
            format.scale = 1
            let renderer = UIGraphicsImageRenderer(size: size, format: format)
            let resized = renderer.image { _ in image.draw(in: CGRect(origin: .zero, size: size)) }
            if let bytes = resized.jpegData(compressionQuality: 0.75) {
                let thumbName = UUID().uuidString + ".jpg"
                do {
                    try bytes.write(to: directory.appendingPathComponent(thumbName),
                                    options: [.atomic, .completeFileProtectionUntilFirstUserAuthentication])
                    thumbnail = "Assets/" + thumbName
                } catch {
                    // The original remains usable even when thumbnail generation fails.
                    thumbnail = nil
                }
            }
        }
        return StoredAsset(path: "Assets/" + name, thumbnailPath: thumbnail)
    }

    static func copy(from url: URL, requireGroup: Bool = false) throws -> StoredAsset {
        let accessing = url.startAccessingSecurityScopedResource()
        defer { if accessing { url.stopAccessingSecurityScopedResource() } }
        let values = try url.resourceValues(forKeys: [.fileSizeKey, .isRegularFileKey, .contentTypeKey])
        guard values.isRegularFile == true else { throw AppError.invalidFile }
        guard (values.fileSize ?? maximumBytes + 1) <= maximumBytes else { throw AppError.fileTooLarge }
        return try save(BoundedFileReader.read(url, maximumBytes: AssetStore.maximumBytes), type: values.contentType ?? UTType(filenameExtension: url.pathExtension) ?? .data,
                        requireGroup: requireGroup)
    }

    static func url(for path: String?) -> URL? {
        guard let root = try? SharedStore.directory() else { return nil }
        return AssetPathPolicy.url(for: path, in: root)
    }

    static func remove(_ asset: StoredAsset) {
        for path in [asset.path, asset.thumbnailPath].compactMap({ $0 }) {
            if let url = url(for: path) { try? FileManager.default.removeItem(at: url) }
        }
    }
}
