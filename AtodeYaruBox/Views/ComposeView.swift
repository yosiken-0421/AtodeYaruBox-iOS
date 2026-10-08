import SwiftUI
import PhotosUI
import UniformTypeIdentifiers
import AVFoundation

struct ComposeView: View {
    @Environment(AppSession.self) private var session
    @Environment(\.dismiss) private var dismiss
    @State private var model = ComposeViewModel()
    @State private var photo: PhotosPickerItem?
    @State private var showingFilePicker = false
    @State private var showingCamera = false
    @State private var photoLoading = false
    @State private var photoTask: Task<Void, Never>?

    var body: some View {
        @Bindable var model = model
        Form {
            Section("追加するもの") {
                TextField("タイトル", text: $model.title, axis: .vertical).accessibilityIdentifier("titleField")
                TextField("メモ", text: $model.note, axis: .vertical).lineLimit(3...10).accessibilityIdentifier("noteField")
                TextField("WebページのURL（任意）", text: $model.urlText)
                    .keyboardType(.URL).textInputAutocapitalization(.never).autocorrectionDisabled()
                    .accessibilityIdentifier("urlField")
            }
            Section("写真・ファイルから") {
                PhotosPicker(selection: $photo, matching: .images) { Label("写真を選ぶ", systemImage: "photo") }
                Button { openCamera() } label: { Label("カメラで撮る", systemImage: "camera") }
                Button { showingFilePicker = true } label: { Label("ファイルを選ぶ", systemImage: "doc") }
                if let asset = model.asset {
                    AttachmentView(path: asset.path, thumbnailPath: asset.thumbnailPath)
                }
                if model.isProcessing || photoLoading { ProgressView("端末内で読み取り中…") }
                if let message = model.importMessage { Text(message).font(.footnote).foregroundStyle(.secondary) }
            }.disabled(model.isProcessing || model.isSaving || photoLoading)
            Section("内容を確認") {
                Picker("種類", selection: $model.action) {
                    ForEach(ActionType.allCases) { action in Label(action.label, systemImage: action.symbol).tag(action) }
                }
                if !model.rawOCRText.isEmpty {
                    Text("読み取った内容を確認し、必要ならタイトル・種類・日時を直してください。年がない日付は今年、時刻がない日付は9:00の候補です。")
                        .font(.footnote).foregroundStyle(.secondary)
                    DisclosureGroup("読み取った原文") { Text(model.rawOCRText).textSelection(.enabled) }
                }
                TextField("タグ（カンマ区切り）", text: $model.tagsText)
            }
            Section("お知らせ") {
                Toggle("日時を設定", isOn: $model.hasDate).accessibilityIdentifier("hasDateToggle")
                if model.hasDate {
                    DatePicker("日時", selection: $model.dueDate, displayedComponents: [.date, .hourAndMinute])
                    Picker("通知の強さ", selection: $model.reminderMode) {
                        ForEach(ReminderMode.allCases) { mode in Text(mode.label).tag(mode) }
                    }
                }
            }
            Section {
                Button { save() } label: {
                    if model.isSaving { ProgressView("保存中…") }
                    else { Label("箱に保存", systemImage: "tray.and.arrow.down").frame(maxWidth: .infinity, minHeight: 44) }
                }.buttonStyle(.borderedProminent).tint(.boxButton).disabled(!model.canSave || photoLoading).accessibilityIdentifier("saveButton")
            }
        }
        .navigationTitle("新しく追加")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .cancellationAction) {
                Button("キャンセル") { dismiss() }.disabled(model.isSaving || model.isProcessing || photoLoading)
            }
            ToolbarItem(placement: .confirmationAction) {
                Button("保存") { save() }.disabled(!model.canSave || photoLoading).accessibilityIdentifier("toolbarSaveButton")
            }
        }
        .interactiveDismissDisabled(model.isProcessing || model.isSaving || photoLoading)
        .onDisappear { photoTask?.cancel(); model.discardUnsavedAsset() }
        .onChange(of: photo) { _, item in
            guard let item else { return }
            photoTask?.cancel()
            photoLoading = true
            photoTask = Task {
                defer { photoLoading = false }
                do {
                    guard let bytes = try await item.loadTransferable(type: Data.self) else { return }
                    try Task.checkCancellation()
                    await model.importData(bytes, type: item.supportedContentTypes.first ?? .image, source: .photo)
                    photo = nil
                } catch { model.errorMessage = "写真を読み込めませんでした。別の写真をお試しください。" }
            }
        }
        .fileImporter(isPresented: $showingFilePicker, allowedContentTypes: [.item], allowsMultipleSelection: false) { result in
            switch result {
            case .success(let urls): if let url = urls.first { Task { await model.importFile(url) } }
            case .failure(let error): model.errorMessage = error.localizedDescription
            }
        }
        .sheet(isPresented: $showingCamera) {
            CameraPicker { bytes in Task { await model.importData(bytes, type: .jpeg, source: .camera) } }
        }
        .alert("入力を確認してください", isPresented: Binding(
            get: { model.errorMessage != nil }, set: { if !$0 { model.errorMessage = nil } })) {
            Button("閉じる", role: .cancel) { model.errorMessage = nil }
        } message: { Text(model.errorMessage ?? "") }
    }
    private func save() { Task { if await model.save(to: session) { dismiss() } } }
    private func openCamera() {
        guard UIImagePickerController.isSourceTypeAvailable(.camera) else { model.errorMessage = "この端末ではカメラを使えません。写真を選んでください。"; return }
        Task {
            let status = AVCaptureDevice.authorizationStatus(for: .video)
            var allowed = status == .authorized
            if status == .notDetermined { allowed = await AVCaptureDevice.requestAccess(for: .video) }
            if allowed { showingCamera = true }
            else { model.errorMessage = "カメラを使う場合はiPhoneの設定でカメラを許可してください。" }
        }
    }
}
