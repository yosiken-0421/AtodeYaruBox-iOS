import Foundation
import CoreGraphics
import CoreText
import ImageIO
import Vision

enum FixtureError: Error { case arguments, bitmap, image, destination, write, unreadableFixture }

guard CommandLine.arguments.count == 2 else { throw FixtureError.arguments }
let output = URL(fileURLWithPath: CommandLine.arguments[1])
guard let bitmap = CGContext(data: nil, width: 1500, height: 600,
                            bitsPerComponent: 8, bytesPerRow: 1500 * 4,
                            space: CGColorSpaceCreateDeviceRGB(),
                            bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue) else { throw FixtureError.bitmap }
bitmap.setFillColor(CGColor(gray: 1, alpha: 1))
bitmap.fill(CGRect(x: 0, y: 0, width: 1500, height: 600))
let font = CTFontCreateWithName("Helvetica" as CFString, 56, nil)
let attributes: [NSAttributedString.Key: Any] = [
    NSAttributedString.Key(kCTFontAttributeName as String): font,
    NSAttributedString.Key(kCTForegroundColorAttributeName as String): CGColor(gray: 0, alpha: 1)
]
for (index, text) in ["Return deadline: 2030/10/08 19:00", "Order number: PHOTO123"].enumerated() {
    bitmap.textPosition = CGPoint(x: 60, y: CGFloat(460 - 120 * index))
    let line = CTLineCreateWithAttributedString(NSAttributedString(string: text, attributes: attributes) as CFAttributedString)
    CTLineDraw(line, bitmap)
}
guard let image = bitmap.makeImage() else { throw FixtureError.image }
guard let destination = CGImageDestinationCreateWithURL(output as CFURL, "public.png" as CFString, 1, nil) else {
    throw FixtureError.destination
}
let metadata: [String: Any] = [
    kCGImagePropertyExifDictionary as String: [kCGImagePropertyExifDateTimeOriginal as String: "2030:10:08 19:00:00"],
    kCGImagePropertyTIFFDictionary as String: [kCGImagePropertyTIFFDateTime as String: "2030:10:08 19:00:00",
        kCGImagePropertyTIFFImageDescription as String: "Atode QA PHOTO123"]
]
CGImageDestinationAddImage(destination, image, metadata as CFDictionary)
guard CGImageDestinationFinalize(destination) else { throw FixtureError.write }
let request = VNRecognizeTextRequest()
request.recognitionLevel = .accurate
request.recognitionLanguages = ["en-US"]
try VNImageRequestHandler(cgImage: image, options: [:]).perform([request])
let recognized = (request.results ?? []).compactMap { $0.topCandidates(1).first?.string }.joined(separator: "\n")
guard recognized.contains("PHOTO123"), recognized.contains("2030") else { throw FixtureError.unreadableFixture }
print("Created synthetic photo fixture. No personal image or network used.")
print("Fixture preparation only: Mac Vision found the marker. This is not the iOS UI test result.")
