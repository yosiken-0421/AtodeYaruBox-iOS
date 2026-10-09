// Native text-style metadata and room for the full preferred font line height.
import SwiftUI
import UIKit

@MainActor
struct SearchTextField: UIViewRepresentable {
    @Binding var text: String
    @Binding var isFocused: Bool
    let submit: () -> Void

    func makeCoordinator() -> Coordinator { Coordinator(self) }

    func makeUIView(context: Context) -> UITextField {
        let field = UITextField()
        field.borderStyle = .roundedRect
        field.delegate = context.coordinator
        field.addTarget(context.coordinator, action: #selector(Coordinator.changed), for: .editingChanged)
        field.autocorrectionType = .no
        field.autocapitalizationType = .none
        field.returnKeyType = .search
        field.adjustsFontForContentSizeCategory = true
        field.setContentCompressionResistancePriority(.defaultLow, for: .horizontal)
        field.accessibilityIdentifier = "searchField"
        field.accessibilityLabel = "検索"
        field.accessibilityHint = "タイトル・メモ・読み取った文字を探します"
        return field
    }

    func updateUIView(_ field: UITextField, context: Context) {
        context.coordinator.parent = self
        let category = BoxTypography.category(context.environment.dynamicTypeSize)
        let traits = field.traitCollection.modifyingTraits { $0.preferredContentSizeCategory = category }
        let font = UIFont.preferredFont(forTextStyle: .body, compatibleWith: traits)
        field.font = font
        field.textColor = .label
        field.backgroundColor = .systemBackground
        field.attributedPlaceholder = NSAttributedString(string: "検索",
            attributes: [.font: font, .foregroundColor: UIColor.label])
        if field.text != text { field.text = text }
        if !isFocused && field.isFirstResponder { field.resignFirstResponder() }
        if isFocused && !field.isFirstResponder && field.window != nil { field.becomeFirstResponder() }
        field.invalidateIntrinsicContentSize()
    }

    func sizeThatFits(_ proposal: ProposedViewSize, uiView: UITextField, context: Context) -> CGSize? {
        CGSize(width: max(44, proposal.width ?? uiView.intrinsicContentSize.width),
               height: max(44, (uiView.font?.lineHeight ?? 0) + 18))
    }

    @MainActor final class Coordinator: NSObject, UITextFieldDelegate {
        var parent: SearchTextField
        init(_ parent: SearchTextField) { self.parent = parent }
        @objc func changed(_ field: UITextField) { parent.text = field.text ?? "" }
        func textFieldDidBeginEditing(_ textField: UITextField) {
            if !parent.isFocused { parent.isFocused = true }
        }
        func textFieldDidEndEditing(_ textField: UITextField) {
            if parent.isFocused { parent.isFocused = false }
        }
        func textFieldShouldReturn(_ textField: UITextField) -> Bool {
            parent.submit()
            textField.resignFirstResponder()
            return true
        }
    }
}
