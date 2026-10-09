import SwiftUI
import UIKit

extension Color {
    static var boxAccent: Color { Color("BoxAccent") }
    static var boxButton: Color { Color("BoxButton") }
}

struct BoxActionLabel: View {
    let title: String
    let symbol: String
    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: symbol).foregroundStyle(Color.boxAccent).accessibilityHidden(true)
            Text(title).font(.body.weight(.semibold)).foregroundStyle(Color.primary)
                .fixedSize(horizontal: false, vertical: true)
        }
    }
}

/// Opaque surfaces keep action text legible in both appearances and all font sizes.
struct BoxActionButtonStyle: ButtonStyle {
    var prominent = false
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.body.weight(.semibold))
            .fixedSize(horizontal: false, vertical: true)
            .padding(.horizontal, 14).padding(.vertical, 10)
            .frame(minWidth: 44, minHeight: 44)
            .foregroundStyle(Color.primary)
            .background(Color(.systemBackground), in: RoundedRectangle(cornerRadius: 12))
            .overlay { RoundedRectangle(cornerRadius: 12).strokeBorder(Color.boxAccent, lineWidth: prominent ? 2 : 1.5) }
    }
}

/// Native text-style metadata and flexible sizing for the main accessible actions.
@MainActor
struct BoxActionButton: UIViewRepresentable {
    let title: String
    let symbol: String
    var prominent = false
    let identifier: String
    var hint: String? = nil
    let action: () -> Void

    func makeCoordinator() -> Coordinator { Coordinator(action: action) }
    func makeUIView(context: Context) -> BoxNativeActionButton {
        let button = BoxNativeActionButton(frame: .zero)
        button.addTarget(context.coordinator, action: #selector(Coordinator.activate), for: .touchUpInside)
        button.titleLabel?.adjustsFontForContentSizeCategory = true
        button.titleLabel?.numberOfLines = 0
        button.titleLabel?.lineBreakMode = .byWordWrapping
        button.contentHorizontalAlignment = .leading
        configure(button, context: context)
        return button
    }
    func updateUIView(_ button: BoxNativeActionButton, context: Context) {
        context.coordinator.action = action
        configure(button, context: context)
        button.invalidateIntrinsicContentSize()
    }
    func sizeThatFits(_ proposal: ProposedViewSize, uiView: BoxNativeActionButton, context: Context) -> CGSize? {
        let width = max(44, proposal.width ?? uiView.intrinsicContentSize.width)
        let fitted = uiView.sizeThatFits(CGSize(width: width, height: .greatestFiniteMagnitude))
        return CGSize(width: width, height: max(44, fitted.height))
    }
    private func configure(_ button: BoxNativeActionButton, context: Context) {
        button.textStyle = prominent ? .headline : .body
        button.symbolName = symbol
        let accent = UIColor(named: "BoxAccent") ?? .systemTeal
        var configuration = UIButton.Configuration.plain()
        configuration.title = title
        configuration.imagePadding = 8
        configuration.titleLineBreakMode = .byWordWrapping
        configuration.contentInsets = NSDirectionalEdgeInsets(top: 12, leading: 14, bottom: 12, trailing: 14)
        configuration.baseForegroundColor = .label
        configuration.background.backgroundColor = .systemBackground
        configuration.background.strokeColor = accent
        configuration.background.strokeWidth = prominent ? 2 : 1.5
        configuration.background.cornerRadius = 12
        button.configuration = configuration
        button.setNeedsUpdateConfiguration()
        button.isEnabled = context.environment.isEnabled
        button.titleLabel?.adjustsFontForContentSizeCategory = true
        button.titleLabel?.numberOfLines = 0
        button.titleLabel?.lineBreakMode = .byWordWrapping
        button.isAccessibilityElement = true
        button.accessibilityIdentifier = identifier
        button.accessibilityLabel = title
        button.accessibilityHint = hint
    }
    @MainActor final class Coordinator: NSObject {
        var action: () -> Void
        init(action: @escaping () -> Void) { self.action = action }
        @objc func activate() { action() }
    }
}

/// Keep native font metadata and individual reading elements in status rows.
@MainActor
struct BoxStatusText: UIViewRepresentable {
    let text: String
    var headline = false
    let identifier: String
    var textStyle: UIFont.TextStyle? = nil
    var centered = false
    var background: UIColor = .secondarySystemGroupedBackground

    func makeUIView(context: Context) -> BoxNativeStatusLabel {
        let label = BoxNativeStatusLabel(frame: .zero)
        label.numberOfLines = 0
        label.lineBreakMode = .byWordWrapping
        label.adjustsFontForContentSizeCategory = true
        label.isAccessibilityElement = true
        label.accessibilityTraits = .staticText
        updateUIView(label, context: context)
        return label
    }
    func updateUIView(_ label: BoxNativeStatusLabel, context: Context) {
        label.textStyle = textStyle ?? (headline ? .headline : .body)
        label.bold = headline
        label.updateFont()
        label.text = text
        label.textAlignment = centered ? .center : .natural
        label.textColor = .label
        label.backgroundColor = background
        label.accessibilityTraits = headline ? [.staticText, .header] : .staticText
        label.accessibilityIdentifier = identifier
        label.accessibilityLabel = text
        label.invalidateIntrinsicContentSize()
    }
    func sizeThatFits(_ proposal: ProposedViewSize, uiView: BoxNativeStatusLabel, context: Context) -> CGSize? {
        let width = max(1, proposal.width ?? uiView.intrinsicContentSize.width)
        let fitted = uiView.sizeThatFits(CGSize(width: width, height: .greatestFiniteMagnitude))
        return CGSize(width: width, height: fitted.height)
    }
}

enum BoxTypography {
    static func category(_ size: DynamicTypeSize) -> UIContentSizeCategory {
        switch size {
        case .xSmall: return .extraSmall
        case .small: return .small
        case .medium: return .medium
        case .large: return .large
        case .xLarge: return .extraLarge
        case .xxLarge: return .extraExtraLarge
        case .xxxLarge: return .extraExtraExtraLarge
        case .accessibility1: return .accessibilityMedium
        case .accessibility2: return .accessibilityLarge
        case .accessibility3: return .accessibilityExtraLarge
        case .accessibility4: return .accessibilityExtraExtraLarge
        case .accessibility5: return .accessibilityExtraExtraExtraLarge
        default: return .large
        }
    }
}
