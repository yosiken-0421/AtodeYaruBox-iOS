import UIKit

/// Read the live UIKit traits when a system text-size change reaches the view.
/// A configuration transformer must not retain a font from an earlier size.
@MainActor
final class BoxNativeActionButton: UIButton {
    var textStyle: UIFont.TextStyle = .body
    var symbolName = ""

    override init(frame: CGRect) {
        super.init(frame: frame)
        registerForTraitChanges([UITraitPreferredContentSizeCategory.self, UITraitLegibilityWeight.self]) {
            (button: BoxNativeActionButton, _: UITraitCollection) in
            button.setNeedsUpdateConfiguration()
            button.invalidateIntrinsicContentSize()
        }
    }

    required init?(coder: NSCoder) { fatalError("Created programmatically") }

    override func updateConfiguration() {
        super.updateConfiguration()
        guard var current = configuration else { return }
        let font = UIFont.preferredFont(forTextStyle: textStyle, compatibleWith: traitCollection)
        let accent = UIColor(named: "BoxAccent") ?? .systemTeal
        current.image = UIImage(systemName: symbolName, withConfiguration: UIImage.SymbolConfiguration(font: font))?
            .withTintColor(accent, renderingMode: .alwaysOriginal)
        current.titleTextAttributesTransformer = UIConfigurationTextAttributesTransformer { incoming in
            var attributes = incoming
            attributes.font = font
            attributes.foregroundColor = .label
            return attributes
        }
        configuration = current
        titleLabel?.adjustsFontForContentSizeCategory = true
        invalidateIntrinsicContentSize()
    }
}

@MainActor
final class BoxNativeStatusLabel: UILabel {
    var textStyle: UIFont.TextStyle = .body
    var bold = false

    override init(frame: CGRect) {
        super.init(frame: frame)
        adjustsFontForContentSizeCategory = true
        registerForTraitChanges([UITraitPreferredContentSizeCategory.self, UITraitLegibilityWeight.self]) {
            (label: BoxNativeStatusLabel, _: UITraitCollection) in
            label.updateFont()
        }
    }

    required init?(coder: NSCoder) { fatalError("Created programmatically") }

    func updateFont() {
        let preferred = UIFont.preferredFont(forTextStyle: textStyle, compatibleWith: traitCollection)
        if bold, let descriptor = preferred.fontDescriptor.withSymbolicTraits(.traitBold) {
            font = UIFont(descriptor: descriptor, size: preferred.pointSize)
        } else {
            font = preferred
        }
        invalidateIntrinsicContentSize()
    }
}
