import SwiftUI

struct EditItemView: View {
    let item: InboxItem
    @Environment(AppSession.self) private var session
    @Environment(\.dismiss) private var dismiss
    @State private var draft: ItemDraft
    @State private var errorMessage: String?
    init(item: InboxItem) { self.item = item; _draft = State(initialValue: ItemDraft(item)) }
    var body: some View {
        Form {
            Section("内容") {
                TextField("タイトル", text: $draft.title, axis: .vertical)
                TextField("メモ", text: $draft.note, axis: .vertical).lineLimit(3...10)
                Picker("種類", selection: $draft.action) {
                    ForEach(ActionType.allCases) { action in Label(action.label, systemImage: action.symbol).tag(action) }
                }
                TextField("URL", text: $draft.url).keyboardType(.URL).textInputAutocapitalization(.never).autocorrectionDisabled()
                TextField("タグ（カンマ区切り）", text: $draft.tags)
            }
            Section("日時・通知") {
                Toggle("日時を設定", isOn: $draft.hasDate)
                if draft.hasDate { DatePicker("日時", selection: $draft.date) }
                Picker("通知の強さ", selection: $draft.mode) {
                    ForEach(ReminderMode.allCases) { mode in Text(mode.label).tag(mode) }
                }
            }
            Section("読み取った情報を修正") {
                TextField("商品名", text: $draft.product)
                TextField("金額", text: $draft.price)
                TextField("店名・場所", text: $draft.place)
                TextField("住所", text: $draft.address)
                TextField("電話番号", text: $draft.phone)
                TextField("メール", text: $draft.email).textInputAutocapitalization(.never)
                TextField("注文番号", text: $draft.orderNumber)
                TextField("予約番号", text: $draft.reservationNumber)
                Toggle("返品期限を設定", isOn: $draft.hasReturnDeadline)
                if draft.hasReturnDeadline { DatePicker("返品期限", selection: $draft.returnDeadline) }
            }
        }
        .navigationTitle("編集").navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .cancellationAction) { Button("キャンセル") { dismiss() } }
            ToolbarItem(placement: .confirmationAction) {
                Button("保存") {
                    Task {
                        do {
                            guard !draft.title.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { throw AppError.emptyTitle }
                            if !draft.url.isEmpty && URLValidator.webURL(draft.url) == nil { throw AppError.invalidURL }
                            try session.repository.update(item) { draft.apply(to: $0) }
                            if draft.hasDate && item.status.isOpen { await session.requestNotifications() }
                            session.refreshSideEffects(); dismiss()
                        } catch { errorMessage = error.localizedDescription }
                    }
                }
            }
        }
        .alert("入力を確認してください", isPresented: Binding(get: { errorMessage != nil }, set: { if !$0 { errorMessage = nil } })) {
            Button("閉じる", role: .cancel) { errorMessage = nil }
        } message: { Text(errorMessage ?? "") }
    }
}

private struct ItemDraft {
    var title: String; var note: String; var action: ActionType; var url: String; var tags: String
    var hasDate: Bool; var date: Date; var mode: ReminderMode
    var product: String; var price: String; var place: String; var address: String
    var phone: String; var email: String; var orderNumber: String; var reservationNumber: String
    var hasReturnDeadline: Bool; var returnDeadline: Date
    init(_ item: InboxItem) {
        title = item.title; note = item.note; action = item.actionType; url = item.sourceURL ?? ""
        tags = item.tags.joined(separator: ", "); hasDate = item.dueDate != nil; date = item.dueDate ?? Date().addingTimeInterval(3600)
        mode = item.reminderMode; product = item.extractedProductName ?? ""; price = item.extractedPrice ?? ""
        place = item.extractedPlace ?? ""; address = item.extractedAddress ?? ""; phone = item.extractedPhone ?? ""
        email = item.extractedEmail ?? ""; orderNumber = item.extractedOrderNumber ?? ""
        reservationNumber = item.extractedReservationNumber ?? ""
        hasReturnDeadline = item.extractedReturnDeadline != nil; returnDeadline = item.extractedReturnDeadline ?? date
    }
    func apply(to item: InboxItem) {
        func optional(_ value: String) -> String? {
            let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
            return trimmed.isEmpty ? nil : trimmed
        }
        item.title = title.trimmingCharacters(in: .whitespacesAndNewlines); item.note = note
        item.actionType = action; item.sourceURL = optional(url); item.dueDate = hasDate ? date : nil
        item.reminderMode = mode; item.tags = tags.split(separator: ",").compactMap { optional(String($0)) }
        item.extractedProductName = optional(product); item.extractedPrice = optional(price)
        item.extractedPlace = optional(place); item.extractedAddress = optional(address)
        item.extractedPhone = optional(phone); item.extractedEmail = optional(email)
        item.extractedOrderNumber = optional(orderNumber); item.extractedReservationNumber = optional(reservationNumber)
        item.extractedReturnDeadline = hasReturnDeadline ? returnDeadline : nil
        if item.status == .inbox { item.status = .active }
    }
}
