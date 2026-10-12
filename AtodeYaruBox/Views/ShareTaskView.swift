import SwiftUI

struct ShareTaskView: View {
    let item: InboxItem
    @Environment(\.dismiss) private var dismiss
    @State private var includeNote = false
    @State private var includeURL = false
    @State private var includeDate = true

    private var document: SharedTaskDocument {
        SharedTaskDocument(title: item.title, note: includeNote ? item.note : "", action: item.actionType,
                           dueDate: includeDate ? item.dueDate : nil,
                           sourceURL: includeURL ? item.sourceURL.flatMap(URLValidator.webURL)?.absoluteString : nil)
    }
    private var validationMessage: String? {
        do { _ = try SharedTaskCodec.encode(document); return nil }
        catch { return "共有するタイトルは160文字、メモは32KBまでです。詳細の「編集」で短くしてから共有してください。" }
    }
    var body: some View {
        Form {
            Section("共有する内容") {
                if item.dueDate != nil { Toggle("日時を含める", isOn: $includeDate).accessibilityIdentifier("shareDateToggle") }
                if !item.note.isEmpty { Toggle("メモを含める", isOn: $includeNote).accessibilityIdentifier("shareNoteToggle") }
                if item.sourceURL.flatMap(URLValidator.webURL) != nil { Toggle("WebページのURLを含める", isOn: $includeURL) }
                Text("写真・添付ファイル・読み取った原文は含まれません。")
                    .font(.footnote).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
            }
            Section("相手に渡す内容") {
                Text(SharedTaskCodec.text(document)).textSelection(.enabled).accessibilityIdentifier("sharePreview")
            }
            Section("共有方法") {
                ShareLink(item: SharedTaskCodec.text(document)) {
                    Label("文章で共有", systemImage: "square.and.arrow.up").frame(minHeight: 44)
                }.accessibilityIdentifier("shareTextButton").disabled(validationMessage != nil)
                ShareLink(item: TaskShareExport(document: document), preview: SharePreview(item.title)) {
                    Label("箱に取り込めるファイルで共有", systemImage: "tray.and.arrow.up").frame(minHeight: 44)
                }.accessibilityIdentifier("shareFileButton").disabled(validationMessage != nil)
                Text("相手も「あとでやる箱」を使っていれば、ファイルを開いて自分の箱へ保存できます。相手にコピーを渡すため、完了や変更は同期されません。")
                    .font(.footnote).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
                if let validationMessage { Label(validationMessage, systemImage: "exclamationmark.triangle") }
            }
        }
        .navigationTitle("項目を共有").navigationBarTitleDisplayMode(.inline)
        .toolbar { ToolbarItem(placement: .cancellationAction) { Button("閉じる") { dismiss() } } }
    }
}
