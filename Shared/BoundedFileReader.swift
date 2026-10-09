import Foundation

enum BoundedFileReader {
    static func read(_ url: URL, maximumBytes: Int) throws -> Data {
        guard maximumBytes >= 0, url.isFileURL else { throw AppError.invalidFile }
        let values = try url.resourceValues(forKeys: [.isRegularFileKey, .fileSizeKey])
        guard values.isRegularFile == true else { throw AppError.invalidFile }
        if let size = values.fileSize, size > maximumBytes { throw AppError.fileTooLarge }
        let handle = try FileHandle(forReadingFrom: url)
        defer { try? handle.close() }
        var data = Data()
        data.reserveCapacity(min(max(0, values.fileSize ?? 0), maximumBytes))
        while true {
            // Read one extra byte at the boundary to detect growth during reading.
            let remaining = maximumBytes - data.count
            let chunkSize = remaining >= 65536 ? 65536 : remaining + 1
            guard let chunk = try handle.read(upToCount: chunkSize), !chunk.isEmpty else { return data }
            guard chunk.count <= remaining else { throw AppError.fileTooLarge }
            data.append(chunk)
        }
    }
}
