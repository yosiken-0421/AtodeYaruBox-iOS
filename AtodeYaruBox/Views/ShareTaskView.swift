import SwiftUI

struct ShareTaskView: View {
    let item: InboxItem
    @Environment(\.dismiss) private var dismiss
    @State private var includeNote = false
    @State private var includeURL = false
    @State private var includeDate = true
    @State private var activity: ShareActivityPayload?
    @State private var sharingError: String?

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
            Section {
                BoxActionButton(title: "閉じる", symbol: "xmark.circle", identifier: "shareCloseButton") { dismiss() }
            }
            Section {
                if item.dueDate != nil { choice("日時", value: $includeDate, identifier: "shareDateToggle") }
                if !item.note.isEmpty { choice("メモ", value: $includeNote, identifier: "shareNoteToggle") }
                if item.sourceURL.flatMap(URLValidator.webURL) != nil { choice("WebページのURL", value: $includeURL, identifier: "shareURLToggle") }
                BoxStatusText(text: "写真・添付ファイル・読み取った原文は含まれません。",
                              identifier: "sharePrivacyNotice", textStyle: .footnote)
            } header: {
                header("共有する内容", identifier: "shareContentsHeader")
            }
            Section {
                BoxStatusText(text: SharedTaskCodec.text(document), identifier: "sharePreview")
            } header: {
                header("相手に渡す内容", identifier: "sharePreviewHeader")
            }
            Section {
                BoxActionButton(title: "文章で共有", symbol: "square.and.arrow.up", identifier: "shareTextButton") {
                    activity = ShareActivityPayload(content: .text(SharedTaskCodec.text(document)))
                }.disabled(validationMessage != nil)
                BoxActionButton(title: "箱に取り込めるファイルで共有", symbol: "tray.and.arrow.up", identifier: "shareFileButton") {
                    do { activity = ShareActivityPayload(content: .file(try TaskShareExport(document: document).makeFile())) }
                    catch { sharingError = error.localizedDescription }
                }.disabled(validationMessage != nil)
                BoxStatusText(text: "相手も「あとでやる箱」を使っていれば、ファイルを開いて自分の箱へ保存できます。相手にコピーを渡すため、完了や変更は同期されません。",
                              identifier: "shareCopyNotice", textStyle: .footnote)
                if let validationMessage { Label(validationMessage, systemImage: "exclamationmark.triangle") }
            } header: {
                header("共有方法", identifier: "shareMethodHeader")
            }
        }
        .navigationTitle("項目を共有").navigationBarTitleDisplayMode(.inline)
        .sheet(item: $activity) { payload in ShareActivitySheet(payload: payload) }
        .alert("共有できませんでした", isPresented: Binding(get: { sharingError != nil }, set: { if !$0 { sharingError = nil } })) {
            Button("閉じる", role: .cancel) { sharingError = nil }
        } message: { Text(sharingError ?? "") }
    }
    private func header(_ title: String, identifier: String) -> some View {
        BoxStatusText(text: title, headline: true, identifier: identifier, background: .systemGroupedBackground)
    }
    private func choice(_ title: String, value: Binding<Bool>, identifier: String) -> some View {
        BoxActionButton(title: title + (value.wrappedValue ? "：含める" : "：含めない"),
                        symbol: value.wrappedValue ? "checkmark.square" : "square", identifier: identifier,
                        hint: "押すと共有する内容を切り替えます") { value.wrappedValue.toggle() }
    }
}
