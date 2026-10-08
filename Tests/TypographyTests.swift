import XCTest
import SwiftUI
import UIKit
@testable import AtodeYaruBox

final class TypographyTests: XCTestCase {
    @MainActor func testIncreasingSizeSettingsActuallyIncreaseNativeBodyAndHeadlineFonts() {
        let sizes: [DynamicTypeSize] = [.xSmall, .small, .medium, .large, .xLarge, .xxLarge,
            .xxxLarge, .accessibility1, .accessibility2, .accessibility3, .accessibility4, .accessibility5]
        for style in [UIFont.TextStyle.body, .headline] {
            var previous: CGFloat = 0
            for size in sizes {
                let traits = UITraitCollection(preferredContentSizeCategory: BoxTypography.category(size))
                let font = UIFont.preferredFont(forTextStyle: style, compatibleWith: traits)
                XCTAssertGreaterThan(font.pointSize, previous,
                    "Increasing \(style.rawValue) to \(size) must produce a larger native font")
                previous = font.pointSize
            }
        }
    }
}
