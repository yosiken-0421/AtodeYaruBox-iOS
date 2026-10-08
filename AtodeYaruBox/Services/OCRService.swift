import Foundation
import Vision
import ImageIO
import PDFKit
import UIKit

enum OCRService {
    static func recognize(data: Data) async throws -> String {
        try await Task.detached(priority: .userInitiated) {
            guard let source = CGImageSourceCreateWithData(data as CFData, nil),
                  let image = CGImageSourceCreateThumbnailAtIndex(source, 0, [
                    kCGImageSourceCreateThumbnailFromImageAlways: true,
                    kCGImageSourceThumbnailMaxPixelSize: 3000,
                    kCGImageSourceCreateThumbnailWithTransform: true
                  ] as CFDictionary) else { throw AppError.invalidFile }
            let request = VNRecognizeTextRequest()
            request.recognitionLevel = .accurate
            let supported = try request.supportedRecognitionLanguages()
            request.recognitionLanguages = ["ja-JP", "en-US"].filter { supported.contains($0) }
            request.usesLanguageCorrection = true
            let handler = VNImageRequestHandler(cgImage: image)
            try handler.perform([request])
            return (request.results ?? []).compactMap { $0.topCandidates(1).first?.string }.joined(separator: "\n")
        }.value
    }

    static func recognizePDF(data: Data) async throws -> String {
        guard let document = PDFDocument(data: data) else { throw AppError.invalidFile }
        var pages: [String] = []
        for index in 0..<min(document.pageCount, 10) {
            try Task.checkCancellation()
            guard let page = document.page(at: index) else { continue }
            if let text = page.string, !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                pages.append(text)
            } else {
                // OCR needs the page's text detail, not a compressed preview.
                // Bound the longest edge to the same 3000-pixel image budget.
                let bytes = try renderPageForRecognition(page)
                pages.append(try await recognize(data: bytes))
            }
        }
        return pages.joined(separator: "\n\n")
    }

    private static func renderPageForRecognition(_ page: PDFPage) throws -> Data {
        guard let reference = page.pageRef else { throw AppError.invalidFile }
        let bounds = page.bounds(for: .mediaBox)
        guard bounds.width.isFinite, bounds.height.isFinite,
              bounds.width > 0, bounds.height > 0 else { throw AppError.invalidFile }
        let scale = 3000 / max(bounds.width, bounds.height)
        let size = CGSize(width: max(1, floor(bounds.width * scale)),
                          height: max(1, floor(bounds.height * scale)))
        let target = CGRect(origin: .zero, size: size)
        let format = UIGraphicsImageRendererFormat()
        format.scale = 1
        format.opaque = true
        let image = UIGraphicsImageRenderer(size: size, format: format).image { context in
            UIColor.white.setFill()
            context.fill(target)
            let graphics = context.cgContext
            graphics.translateBy(x: 0, y: size.height)
            graphics.scaleBy(x: 1, y: -1)
            graphics.concatenate(reference.getDrawingTransform(.mediaBox, rect: target,
                                                               rotate: 0, preserveAspectRatio: true))
            graphics.drawPDFPage(reference)
        }
        // Keep the raster lossless. The user's original PDF remains unchanged.
        guard let bytes = image.pngData() else { throw AppError.invalidFile }
        return bytes
    }
}
