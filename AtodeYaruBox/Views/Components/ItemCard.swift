import SwiftUI

struct ItemCard: View {
    let item: InboxItem
    var now = Date()
    let complete: () -> Void
    let snooze: () -> Void
    @State private var showingDetail = false
    @Environment(\.dynamicTypeSize) private var typeSize

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Button { showingDetail = true } label: {
                HStack(alignment: .top, spacing: 12) {
                    if !typeSize.isAccessibilitySize {
                        Image(systemName: item.actionType.symbol).font(.title2).foregroundStyle(Color.boxAccent).accessibilityHidden(true)
                    }
                    VStack(alignment: .leading, spacing: 6) {
                        Text(item.title).font(.headline).foregroundStyle(.primary).fixedSize(horizontal: false, vertical: true)
                        Label(item.actionType.label, systemImage: item.actionType.symbol).font(.subheadline)
                            .foregroundStyle(.primary).fixedSize(horizontal: false, vertical: true)
                        if let date = item.dueDate {
                            Label {
                                Text(date, format: .dateTime.month().day().hour().minute())
                            } icon: { Image(systemName: date < now && item.status.isOpen ? "exclamationmark.triangle" : "calendar") }
                            .foregroundStyle(date < now && item.status.isOpen ? Color.red : Color.primary)
                            .fixedSize(horizontal: false, vertical: true)
                            if date < now && item.status.isOpen { Text("期限切れ").font(.caption).foregroundStyle(.red) }
                        } else { Text("日付未設定").font(.subheadline).foregroundStyle(.primary).fixedSize(horizontal: false, vertical: true) }
                        if item.status == .inbox { Label("確認待ち", systemImage: "questionmark.circle").font(.subheadline) }
                        if !item.note.isEmpty { Text(item.note).font(.subheadline).foregroundStyle(.primary).lineLimit(3) }
                        if item.status == .completed { Label("完了", systemImage: "checkmark.circle.fill").foregroundStyle(.green) }
                        Label("詳細を開く", systemImage: "chevron.right").font(.body)
                            .foregroundStyle(.primary).fixedSize(horizontal: false, vertical: true)
                    }
                    if !typeSize.isAccessibilitySize, let url = AssetStore.url(for: item.thumbnailPath),
                       let image = UIImage(contentsOfFile: url.path) {
                        Image(uiImage: image).resizable().scaledToFill().frame(width: 56, height: 56)
                            .clipShape(RoundedRectangle(cornerRadius: 10)).accessibilityHidden(true)
                    }
                }
            }
            .buttonStyle(.plain)
            .accessibilityHint("詳細を開きます")
            if item.status.isOpen {
                if typeSize.isAccessibilitySize {
                    VStack(alignment: .leading, spacing: 12) { actionButtons }
                } else {
                    ViewThatFits(in: .horizontal) {
                        HStack(spacing: 12) { actionButtons }
                        VStack(alignment: .leading, spacing: 8) { actionButtons }
                    }
                }
            }
        }
        .padding(.vertical, 8)
        .accessibilityElement(children: .contain)
        .navigationDestination(isPresented: $showingDetail) { ItemDetailView(item: item) }
    }
    @ViewBuilder private var actionButtons: some View {
        BoxActionButton(title: "完了", symbol: "checkmark", prominent: true, identifier: "completeButton",
            hint: "「\(item.title)」を完了します", action: complete)
        BoxActionButton(title: "あとで", symbol: "clock", identifier: "snoozeButton",
            hint: "「\(item.title)」のお知らせ日時を変更します", action: snooze)
    }
}
