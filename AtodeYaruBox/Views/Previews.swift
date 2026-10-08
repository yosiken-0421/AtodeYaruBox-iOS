#if DEBUG
import SwiftUI

private struct PreviewHost: View {
    @State private var session: AppSession?
    @State private var message: String?
    var body: some View {
        Group {
            if let session {
                NavigationStack { BoxView() }.environment(session).modelContainer(session.container).tint(.boxAccent)
            } else if let message { Text(message) }
            else { ProgressView("プレビューを準備中") }
        }.task {
            guard session == nil, message == nil else { return }
            do {
                let preview = AppSession(container: try SharedStore.container(inMemory: true))
                let overdue = InboxItem(title: "図書館の本を返す", note: "貸出カードも持っていく", actionType: .returnItem,
                                        dueDate: Date().addingTimeInterval(-3600))
                let today = InboxItem(title: "家族へ返事する", actionType: .reply, dueDate: SnoozeCalculator.date(for: .hour))
                let review = InboxItem(title: "共有したWebページ", actionType: .read); review.status = .inbox
                let memo = InboxItem(title: "気になった本を読む", note: "時間がある時に第1章から", actionType: .read)
                for item in [overdue, today, review, memo] { try preview.repository.insert(item) }
                preview.items = try preview.repository.all()
                session = preview
            } catch { message = error.localizedDescription }
        }
    }
}

#Preview("箱・Light") { PreviewHost().preferredColorScheme(.light) }
#Preview("箱・Dark") { PreviewHost().preferredColorScheme(.dark) }
#Preview("箱・大きな文字") { PreviewHost().dynamicTypeSize(.accessibility3) }
#endif
