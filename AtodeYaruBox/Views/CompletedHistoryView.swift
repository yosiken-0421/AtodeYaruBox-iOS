import SwiftUI
import SwiftData

struct CompletedHistoryView: View {
    @Environment(AppSession.self) private var session
    private var items: [InboxItem] { session.items.sorted { ($0.completedAt ?? .distantPast) > ($1.completedAt ?? .distantPast) } }
    var body: some View {
        let completed = items.filter { $0.status == .completed }
        List {
            if completed.isEmpty {
                ContentUnavailableView("完了した項目はありません", systemImage: "checkmark.circle",
                                       description: Text("終わらせた項目は、ここで振り返れます。"))
            }
            ForEach(completed) { item in
                VStack(alignment: .leading, spacing: 12) {
                    NavigationLink { ItemDetailView(item: item) } label: {
                        VStack(alignment: .leading, spacing: 6) {
                            Label(item.title, systemImage: "checkmark.circle.fill")
                            if let date = item.completedAt { Text(date, style: .date).font(.footnote).foregroundStyle(.secondary) }
                        }
                    }
                    Button { session.reopen(item) } label: { Label("未完了に戻す", systemImage: "arrow.uturn.backward") }
                        .buttonStyle(.bordered).frame(minHeight: 44)
                }.padding(.vertical, 6)
            }
        }.navigationTitle("完了履歴")
    }
}
