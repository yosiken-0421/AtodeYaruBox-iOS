import SwiftUI
import UIKit

/// Native button title and subtitle fonts remain identifiable during size changes.
struct CalendarDayButton: UIViewRepresentable {
    let number: Int
    let count: Int
    let today: Bool
    let selected: Bool
    let spokenDate: String
    let action: () -> Void

    func makeCoordinator() -> Coordinator { Coordinator(action) }
    func makeUIView(context: Context) -> BoxNativeActionButton {
        let button = BoxNativeActionButton(frame: .zero)
        button.addTarget(context.coordinator, action: #selector(Coordinator.activate), for: .touchUpInside)
        updateUIView(button, context: context)
        return button
    }
    func updateUIView(_ button: BoxNativeActionButton, context: Context) {
        context.coordinator.action = action
        button.textStyle = selected ? .headline : .body
        button.subtitleTextStyle = .caption1
        button.symbolName = ""
        var configuration = UIButton.Configuration.plain()
        configuration.title = String(number)
        configuration.subtitle = "\(count)件" + (today ? "\n今日" : selected ? "\n✓" : "")
        configuration.titleAlignment = .center
        configuration.titleLineBreakMode = .byWordWrapping
        configuration.subtitleLineBreakMode = .byWordWrapping
        configuration.titlePadding = 4
        configuration.contentInsets = NSDirectionalEdgeInsets(top: 4, leading: 2, bottom: 4, trailing: 2)
        let accent = UIColor(named: "BoxAccent") ?? .systemTeal
        configuration.background.backgroundColor = selected ? accent.withAlphaComponent(0.12) : .clear
        configuration.background.strokeColor = selected ? accent : .clear
        configuration.background.strokeWidth = selected ? 2 : 0
        configuration.background.cornerRadius = 8
        button.configuration = configuration
        button.contentHorizontalAlignment = .center
        button.titleLabel?.adjustsFontForContentSizeCategory = true
        button.titleLabel?.numberOfLines = 0
        button.isAccessibilityElement = true
        button.accessibilityIdentifier = "calendarDay_\(number)"
        button.accessibilityLabel = spokenDate + "、\(count)件" + (today ? "、今日" : "")
        button.accessibilityHint = "この日の項目を表示します"
        button.accessibilityTraits = selected ? [.button, .selected] : .button
        button.setNeedsUpdateConfiguration()
        button.invalidateIntrinsicContentSize()
    }
    func sizeThatFits(_ proposal: ProposedViewSize, uiView: BoxNativeActionButton, context: Context) -> CGSize? {
        let width = max(44, proposal.width ?? 44)
        let fit = uiView.sizeThatFits(CGSize(width: width, height: .greatestFiniteMagnitude))
        return CGSize(width: width, height: max(76, fit.height))
    }
    @MainActor final class Coordinator: NSObject {
        var action: () -> Void
        init(_ action: @escaping () -> Void) { self.action = action }
        @objc func activate() { action() }
    }
}
