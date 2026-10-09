import XCTest
import SwiftUI
import UIKit
@testable import AtodeYaruBox

final class TypographyTests: XCTestCase {
    @MainActor func testIncreasingSizeSettingsActuallyIncreaseNativeBodyAndHeadlineFonts() async {
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

        // Exercise the real controls after attachment, including changes while
        // a presented screen is already visible rather than just font lookup.
        let controller = UIViewController()
        let window = UIWindow(frame: CGRect(x: 0, y: 0, width: 390, height: 844))
        window.rootViewController = controller
        window.isHidden = false
        defer { window.isHidden = true }
        let label = BoxNativeStatusLabel(frame: CGRect(x: 0, y: 0, width: 350, height: 100))
        label.text = "通知の知らせ方"
        label.textStyle = .title2
        label.bold = true
        controller.view.addSubview(label)
        let button = BoxNativeActionButton(frame: CGRect(x: 0, y: 120, width: 350, height: 150))
        button.textStyle = .headline
        button.symbolName = "bell"
        var configuration = UIButton.Configuration.plain()
        configuration.title = "普通（選択中）"
        button.configuration = configuration
        controller.view.addSubview(button)
        var lastLabel: CGFloat = 0
        var lastButton: CGFloat = 0
        for size in sizes {
            controller.traitOverrides.preferredContentSizeCategory = BoxTypography.category(size)
            controller.view.setNeedsLayout()
            controller.view.layoutIfNeeded()
            await Task.yield()
            button.layoutIfNeeded()
            let labelSize = label.font.pointSize
            let buttonSize = button.titleLabel?.font.pointSize ?? 0
            XCTAssertGreaterThan(labelSize, lastLabel, "The displayed heading must follow a live change to \(size)")
            XCTAssertGreaterThan(buttonSize, lastButton, "The displayed button must follow a live change to \(size)")
            XCTAssertTrue(label.adjustsFontForContentSizeCategory)
            XCTAssertTrue(button.titleLabel?.adjustsFontForContentSizeCategory == true)
            lastLabel = labelSize
            lastButton = buttonSize
        }
    }
}
