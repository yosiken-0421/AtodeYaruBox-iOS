import SwiftUI

struct NotificationModeSheet: View {
    @Binding var selectedRawValue: String
    @Environment(\.dismiss) private var dismiss
    @Environment(\.dynamicTypeSize) private var typeSize

    var body: some View {
        NavigationStack {
            List {
                Section {
                    BoxStatusText(text: "通知の知らせ方", headline: true, identifier: "reminderModeSheetTitle", textStyle: .title2)
                }
                Section {
                    BoxStatusText(text: "知らせ方", headline: true, identifier: "reminderModeChoicesHeading")
                    ForEach(ReminderMode.allCases) { mode in
                        BoxActionButton(title: mode.label + (mode.rawValue == selectedRawValue ? "（選択中）" : ""),
                            symbol: mode.rawValue == selectedRawValue ? "checkmark" : "bell",
                            prominent: true,
                            identifier: "reminderModeChoice_" + mode.rawValue,
                            hint: mode.rawValue == selectedRawValue ? "現在の設定です" : "この知らせ方にします") {
                                selectedRawValue = mode.rawValue
                                dismiss()
                            }
                    }
                }
                Section {
                    BoxStatusText(text: "新しく保存する項目の知らせ方を選びます。", identifier: "reminderModeExplanation")
                    BoxStatusText(text: "集中モードやiPhoneの通知設定により、通知が遅れることがあります。",
                        identifier: "reminderModeSystemNotice")
                    BoxActionButton(title: "閉じる", symbol: "xmark", identifier: "reminderModeCloseButton") { dismiss() }
                }
            }.font(.body).foregroundStyle(Color.primary)
                .navigationTitle(typeSize.isAccessibilitySize ? "" : "通知")
                .navigationBarTitleDisplayMode(.inline)
        }.tint(.boxAccent)
    }
}
