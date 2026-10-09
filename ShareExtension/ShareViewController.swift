import SwiftUI
import SwiftData
import UIKit

@MainActor
final class ShareViewController: UIViewController {
    override func viewDidLoad() {
        super.viewDidLoad()
        let providers = (extensionContext?.inputItems as? [NSExtensionItem] ?? []).flatMap { $0.attachments ?? [] }
        let host = UIHostingController(rootView: ShareSaveView(providers: providers, context: extensionContext))
        addChild(host); view.addSubview(host.view)
        host.view.translatesAutoresizingMaskIntoConstraints = false
        NSLayoutConstraint.activate([
            host.view.topAnchor.constraint(equalTo: view.topAnchor), host.view.bottomAnchor.constraint(equalTo: view.bottomAnchor),
            host.view.leadingAnchor.constraint(equalTo: view.leadingAnchor), host.view.trailingAnchor.constraint(equalTo: view.trailingAnchor)
        ])
        host.didMove(toParent: self)
    }
}

private struct ShareSaveView: View {
    let providers: [NSItemProvider]
    let context: NSExtensionContext?
    @State private var drafts: [ShareDraft] = []
    @State private var loading = true
    @State private var saving = false
    @State private var saved = false
    @State private var importFailed = false
    @State private var errorMessage: String?
    private enum Field: Hashable { case title(Int), note(Int) }
    @FocusState private var focusedField: Field?
    private var cannotSave: Bool {
        loading || saving || importFailed || drafts.isEmpty
            || drafts.contains { $0.title.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }
    }
    var body: some View {
        NavigationStack {
            Form {
                if loading { ProgressView("端末内で読み込み中…") }
                ForEach(drafts.indices, id: \.self) { index in
                    Section("保存する内容 \(index + 1)") {
                        TextField("タイトル", text: $drafts[index].title, axis: .vertical)
                            .focused($focusedField, equals: .title(index))
                            .accessibilityIdentifier(index == 0 ? "sharedTitleField" : "sharedTitleField_\(index)")
                        TextField("メモ", text: $drafts[index].note, axis: .vertical).lineLimit(2...6)
                            .focused($focusedField, equals: .note(index))
                        Picker("種類", selection: $drafts[index].action) {
                            ForEach(ActionType.allCases) { action in Text(action.label).tag(action) }
                        }
                    }
                }
                if let errorMessage { Section { Label(errorMessage, systemImage: "exclamationmark.triangle").accessibilityIdentifier("shareImportError") } }
                Section {
                    Button(action: saveDrafts) {
                        Label("箱に保存", systemImage: "tray.and.arrow.down").frame(maxWidth: .infinity, minHeight: 44)
                    }.buttonStyle(.borderedProminent).tint(.boxButton).disabled(cannotSave)
                    Text("共有した項目は「確認待ち」に入ります。日時の設定は、箱で内容を確認してから行えます。")
                        .font(.footnote).foregroundStyle(.secondary)
                }
            }
            .navigationTitle("あとでやる箱").navigationBarTitleDisplayMode(.inline)
            .scrollDismissesKeyboard(.interactively)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("キャンセル") {
                        context?.cancelRequest(withError: NSError(domain: NSCocoaErrorDomain, code: NSUserCancelledError))
                    }.disabled(saving)
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("保存", action: saveDrafts).disabled(cannotSave).accessibilityIdentifier("shareToolbarSaveButton")
                }
            }
        }
        .tint(.boxAccent)
        .task {
            defer { loading = false }
            do {
                guard !providers.isEmpty else { throw AppError.invalidFile }
                guard providers.count <= 10 else {
                    throw NSError(domain: "Share", code: 10, userInfo: [NSLocalizedDescriptionKey: "一度に共有できるのは10件までです。"])
                }
                for provider in providers {
                    let draft = try await ShareImportService.read(provider)
                    if Task.isCancelled { if let asset = draft.asset { AssetStore.remove(asset) }; return }
                    drafts.append(draft)
                }
            } catch { importFailed = true; errorMessage = error.localizedDescription }
        }
        .onDisappear {
            if !saved { for draft in drafts { if let asset = draft.asset { AssetStore.remove(asset) } } }
        }
    }

    private func saveDrafts() {
        guard !cannotSave else { return }
        focusedField = nil
        saving = true
        do {
            let store = try SharedStore.container(requireGroup: true)
            store.mainContext.autosaveEnabled = false
            let items = try drafts.map { try ShareImportService.item(from: $0) }
            for item in items { store.mainContext.insert(item) }
            try store.mainContext.save()
            saved = true
            if let all = try? InboxRepository(context: store.mainContext).all() {
                try? WidgetSnapshotService.write(items: all)
            }
            context?.completeRequest(returningItems: nil, completionHandler: nil)
        } catch { errorMessage = error.localizedDescription; saving = false }
    }
}
