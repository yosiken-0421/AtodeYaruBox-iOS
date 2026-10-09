import SwiftUI
import SwiftData

struct TodayView: View {
    @Environment(AppSession.self) private var session
    private var items: [InboxItem] { session.items.sorted { ($0.dueDate ?? .distantFuture) < ($1.dueDate ?? .distantFuture) } }
    @State private var snoozing: InboxItem?
    @Environment(\.dynamicTypeSize) private var typeSize
    var body: some View {
        TimelineView(.periodic(from: .now, by: 60)) { timeline in
            let open = items.filter { $0.status.isOpen }
            let overdue = open.filter { ($0.dueDate ?? .distantFuture) < timeline.date }
            let today = open.filter {
                guard let due = $0.dueDate else { return false }
                return due >= timeline.date && Calendar.current.isDate(due, inSameDayAs: timeline.date)
            }
            List {
                if typeSize.isAccessibilitySize && overdue.isEmpty && today.isEmpty { addButton }
                if overdue.isEmpty && today.isEmpty {
                    EmptyBoxState(title: "今日はすっきり", symbol: "sun.max",
                        message: "今日の項目はありません。箱の項目を「あとで」から予定できます。")
                        .listRowBackground(Color.clear)
                }
                if !overdue.isEmpty {
                    Section {
                        ForEach(overdue) { item in
                            ItemCard(item: item, now: timeline.date, complete: { session.complete(item) }, snooze: { snoozing = item })
                        }
                    } header: { Label("期限切れ", systemImage: "exclamationmark.triangle").foregroundStyle(.red) }
                }
                if !today.isEmpty {
                    Section("今日") {
                        ForEach(today) { item in
                            ItemCard(item: item, now: timeline.date, complete: { session.complete(item) }, snooze: { snoozing = item })
                        }
                    }
                }
                if typeSize.isAccessibilitySize && (!overdue.isEmpty || !today.isEmpty) { addButton }
            }
        }
        .navigationTitle("今日")
        .toolbar {
            if !typeSize.isAccessibilitySize {
                Button { session.showingComposer = true } label: { BoxActionLabel(title: "追加", symbol: "plus") }
                    .buttonStyle(BoxActionButtonStyle()).accessibilityIdentifier("todayAddButton")
            }
        }
        .sheet(item: $snoozing) { item in SnoozeSheet(item: item) }
    }
    private var addButton: some View {
        BoxActionButton(title: "追加", symbol: "plus", identifier: "todayAddButton") {
            session.showingComposer = true
        }
    }
}
