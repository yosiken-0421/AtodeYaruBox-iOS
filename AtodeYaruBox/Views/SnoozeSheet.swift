import SwiftUI

struct SnoozeSheet: View {
    let item: InboxItem
    @Environment(AppSession.self) private var session
    @Environment(\.dismiss) private var dismiss
    @State private var customDate = Date().addingTimeInterval(3600)
    @State private var isWorking = false
    @Environment(\.dynamicTypeSize) private var typeSize
    var body: some View {
        NavigationStack {
            List {
                if typeSize.isAccessibilitySize {
                    BoxActionButton(title: "閉じる", symbol: "xmark", identifier: "closeSnoozeButton") { dismiss() }
                }
                Section { Text(item.title).font(.headline).fixedSize(horizontal: false, vertical: true) }
                Section {
                    BoxStatusText(text: "いつ知らせますか？", headline: true, identifier: "snoozeChoicesHeading")
                    ForEach(SnoozeOption.allCases) { option in
                        let date = SnoozeCalculator.date(for: option)
                        Button { postpone(date) } label: {
                            VStack(alignment: .leading, spacing: 4) {
                                Label(option.label, systemImage: "clock").font(.body)
                                    .fixedSize(horizontal: false, vertical: true)
                                Text(date, format: .dateTime.month().day().hour().minute()).font(.body).foregroundStyle(.primary)
                                    .fixedSize(horizontal: false, vertical: true)
                            }.frame(maxWidth: .infinity, minHeight: 44, alignment: .leading)
                                .foregroundStyle(.primary).contentShape(Rectangle())
                        }.buttonStyle(.plain).accessibilityIdentifier("snooze_\(option.rawValue)")
                    }
                }
                Section("日時指定") {
                    DatePicker("日時", selection: $customDate, in: Date()..., displayedComponents: [.date, .hourAndMinute])
                    Button { postpone(customDate) } label: { Label("この日時にする", systemImage: "calendar") }
                        .frame(minHeight: 44)
                }
            }
            .disabled(isWorking)
            .navigationTitle("あとで")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .cancellationAction) {
                if !typeSize.isAccessibilitySize { Button("閉じる") { dismiss() }.font(.body) }
            } }
        }
        .presentationDetents([.large])
        .presentationDragIndicator(.visible)
    }
    private func postpone(_ date: Date) {
        isWorking = true
        Task { await session.snooze(item, until: date); isWorking = false; dismiss() }
    }
}
