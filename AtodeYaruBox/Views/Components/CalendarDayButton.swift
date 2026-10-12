import SwiftUI
import UIKit

/// Keep native font metadata on every number, including during system size audits.
struct CalendarDayButton: UIViewRepresentable {
    let number: Int
    let count: Int
    let today: Bool
    let selected: Bool
    let spokenDate: String
    let action: () -> Void

    func makeCoordinator() -> Coordinator { Coordinator(action) }
    func makeUIView(context: Context) -> CalendarDayControl {
        let control = CalendarDayControl(frame: .zero)
        control.addTarget(context.coordinator, action: #selector(Coordinator.activate), for: .touchUpInside)
        updateUIView(control, context: context)
        return control
    }
    func updateUIView(_ control: CalendarDayControl, context: Context) {
        context.coordinator.action = action
        control.number.text = String(number)
        control.number.bold = selected
        control.number.updateFont()
        control.count.text = "\(count)件"
        control.mark.text = today ? "今日" : selected ? "✓" : ""
        control.mark.isHidden = !today && !selected
        control.accessibilityIdentifier = "calendarDay_\(number)"
        control.accessibilityLabel = spokenDate + "、\(count)件" + (today ? "、今日" : "")
        control.accessibilityHint = "この日の項目を表示します"
        control.accessibilityTraits = selected ? [.button, .selected] : .button
        let accent = UIColor(named: "BoxAccent") ?? .systemTeal
        control.backgroundColor = selected ? accent.withAlphaComponent(0.12) : .clear
        control.layer.borderColor = selected ? accent.cgColor : UIColor.clear.cgColor
        control.invalidateIntrinsicContentSize()
    }
    func sizeThatFits(_ proposal: ProposedViewSize, uiView: CalendarDayControl, context: Context) -> CGSize? {
        let width = max(44, proposal.width ?? 44)
        let height = uiView.stack.systemLayoutSizeFitting(CGSize(width: width - 4, height: 0),
            withHorizontalFittingPriority: .required, verticalFittingPriority: .fittingSizeLevel).height
        return CGSize(width: width, height: max(76, height + 8))
    }
    @MainActor final class Coordinator: NSObject {
        var action: () -> Void
        init(_ action: @escaping () -> Void) { self.action = action }
        @objc func activate() { action() }
    }
}

@MainActor final class CalendarDayControl: UIControl {
    let number = BoxNativeStatusLabel(frame: .zero)
    let count = BoxNativeStatusLabel(frame: .zero)
    let mark = BoxNativeStatusLabel(frame: .zero)
    let stack = UIStackView()

    override init(frame: CGRect) {
        super.init(frame: frame)
        isAccessibilityElement = true
        layer.cornerRadius = 8
        layer.borderWidth = 2
        stack.axis = .vertical
        stack.alignment = .fill
        stack.spacing = 4
        stack.isUserInteractionEnabled = false
        for (label, style) in [(number, UIFont.TextStyle.body), (count, .caption1), (mark, .caption2)] {
            label.textStyle = style
            label.numberOfLines = 0
            label.textAlignment = .center
            label.textColor = .label
            label.isAccessibilityElement = false
            label.updateFont()
            stack.addArrangedSubview(label)
        }
        stack.translatesAutoresizingMaskIntoConstraints = false
        addSubview(stack)
        NSLayoutConstraint.activate([
            stack.leadingAnchor.constraint(equalTo: leadingAnchor, constant: 2),
            stack.trailingAnchor.constraint(equalTo: trailingAnchor, constant: -2),
            stack.centerYAnchor.constraint(equalTo: centerYAnchor),
            stack.topAnchor.constraint(greaterThanOrEqualTo: topAnchor, constant: 4),
            stack.bottomAnchor.constraint(lessThanOrEqualTo: bottomAnchor, constant: -4)
        ])
    }
    override func accessibilityActivate() -> Bool {
        sendActions(for: .touchUpInside)
        return true
    }
    required init?(coder: NSCoder) { return nil }
}
