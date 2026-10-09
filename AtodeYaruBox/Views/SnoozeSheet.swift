import SwiftUI

struct SnoozeSheet: View {
    let item: InboxItem
    @Environment(AppSession.self) private var session
    @Environment(\.dismiss) private var dismiss
    @State private var customDate = Date().addingTimeInterval(3600)
    @State private var isWorking = false
    @State private var showingCustomDate = false
    @Environment(\.dynamicTypeSize) private var typeSize
    var body: some View {
        NavigationStack {
            List {
                if typeSize.isAccessibilitySize {
                    BoxStatusText(text: "あとで", headline: true, identifier: "snoozeSheetTitle", textStyle: .title2)
                    BoxActionButton(title: "閉じる", symbol: "xmark", identifier: "closeSnoozeButton") { dismiss() }
                }
                Section { BoxStatusText(text: item.title, headline: true, identifier: "snoozeItemTitle") }
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
                Section {
                    BoxActionButton(title: "日時を指定", symbol: "calendar", identifier: "customSnoozeDateButton") {
                        showingCustomDate = true
                    }
                }
            }
            .disabled(isWorking)
            .navigationTitle(typeSize.isAccessibilitySize ? "" : "あとで")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar(typeSize.isAccessibilitySize ? .hidden : .visible, for: .navigationBar)
            .toolbar { ToolbarItem(placement: .cancellationAction) {
                if !typeSize.isAccessibilitySize { Button("閉じる") { dismiss() }.font(.body) }
            } }
            .sheet(isPresented: $showingCustomDate) {
                CustomSnoozeSheet(date: $customDate) { date in
                    showingCustomDate = false
                    postpone(date)
                }
            }
        }
        .presentationDetents([.large])
        .presentationDragIndicator(.visible)
    }
    private func postpone(_ date: Date) {
        isWorking = true
        Task { await session.snooze(item, until: date); isWorking = false; dismiss() }
    }
}
