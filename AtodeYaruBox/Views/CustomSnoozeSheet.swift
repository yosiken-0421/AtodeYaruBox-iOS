import SwiftUI

struct CustomSnoozeSheet: View {
    @Binding var date: Date
    let save: (Date) -> Void
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    BoxStatusText(text: "日時を指定", headline: true, identifier: "customSnoozeHeading", textStyle: .title2)
                    DatePicker("日時", selection: $date, in: Date()..., displayedComponents: [.date, .hourAndMinute])
                }
                Section {
                    BoxActionButton(title: "この日時にする", symbol: "calendar", identifier: "customSnoozeSaveButton") { save(date) }
                    BoxActionButton(title: "閉じる", symbol: "xmark", identifier: "customSnoozeCloseButton") { dismiss() }
                }
            }
            .toolbar(.hidden, for: .navigationBar)
        }
    }
}
