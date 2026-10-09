import SwiftUI
import MapKit

struct ItemDetailView: View {
    let item: InboxItem
    @Environment(AppSession.self) private var session
    @Environment(\.openURL) private var openURL
    @State private var showingSnooze = false
    @State private var showingEdit = false
    @State private var showingLocation = false
    @State private var addingCalendar = false
    @State private var copied = false
    var body: some View {
        List {
            Section {
                Text(item.title).font(.title2.bold()).fixedSize(horizontal: false, vertical: true)
                BoxActionButton(title: "編集", symbol: "pencil", identifier: "editItemButton") { showingEdit = true }
                Label(item.actionType.label, systemImage: item.actionType.symbol)
                if let date = item.dueDate { LabeledContent("日時") { Text(date, format: .dateTime.year().month().day().hour().minute()) } }
                if item.status == .inbox {
                    Text("共有した内容を確認してください。種類や日時は編集できます。").foregroundStyle(.secondary)
                    Button {
                        do { try session.repository.update(item) { $0.status = .active }; session.refreshSideEffects() }
                        catch { session.errorMessage = error.localizedDescription }
                    } label: { Label("確認しました", systemImage: "checkmark.circle") }
                }
                if !item.note.isEmpty { Text(item.note).textSelection(.enabled) }
                if !item.tags.isEmpty { LabeledContent("タグ", value: item.tags.joined(separator: "、")) }
            }
            if item.status.isOpen {
                Section("次の操作") {
                    Button { session.complete(item) } label: { Label("完了", systemImage: "checkmark").frame(minHeight: 44) }
                    Button { showingSnooze = true } label: { Label("あとで", systemImage: "clock").frame(minHeight: 44) }
                }
            } else if item.status == .completed {
                Section { Label("完了", systemImage: "checkmark.circle.fill").foregroundStyle(.green) }
            }
            if let url = item.sourceURL.flatMap(URLValidator.webURL) {
                Section("元のページ") {
                    Link(destination: url) { Label("Webページを開く", systemImage: "safari") }
                    Text(url.absoluteString).font(.footnote).textSelection(.enabled)
                }
            }
            if let path = item.localAssetPath {
                Section("保存したファイル") { AttachmentView(path: path, thumbnailPath: item.thumbnailPath) }
            }
            if hasExtractedFields {
                Section("読み取った情報（候補）") {
                    field("商品名", item.extractedProductName)
                    field("金額", item.extractedPrice)
                    field("店名・場所", item.extractedPlace)
                    field("住所", item.extractedAddress)
                    field("電話番号", item.extractedPhone)
                    field("メール", item.extractedEmail)
                    field("注文番号", item.extractedOrderNumber)
                    field("予約番号", item.extractedReservationNumber)
                    if let date = item.extractedReturnDeadline { LabeledContent("返品期限") { Text(date, style: .date) } }
                }
            }
            if item.dueDate != nil {
                Section("カレンダー") {
                    Button {
                        addingCalendar = true
                        Task {
                            defer { addingCalendar = false }
                            do {
                                try await session.calendar.add(item)
                                try session.repository.update(item) { $0.calendarAddedAt = Date() }
                            } catch { session.errorMessage = error.localizedDescription }
                        }
                    } label: {
                        Label(item.calendarAddedAt == nil ? "カレンダーに追加" : "カレンダーに追加済み", systemImage: "calendar.badge.plus")
                    }.disabled(addingCalendar || item.calendarAddedAt != nil)
                }
            }
            if item.extractedAddress != nil || item.extractedPlace != nil {
                Section("地図") {
                    Button { openMap() } label: { Label("地図で開く", systemImage: "map") }
                }
            }
            if item.status.isOpen {
                Section("場所のお知らせ") {
                    Button { showingLocation = true } label: { Label("場所で知らせる", systemImage: "location") }
                    if let location = item.locationReminder {
                        Text("\(location.name)に\(location.onEntry ? "着いたら" : "出たら")")
                        Button {
                            do { try session.repository.update(item) { $0.locationReminder = nil }; session.refreshSideEffects() }
                            catch { session.errorMessage = error.localizedDescription }
                        } label: { Label("場所のお知らせを解除", systemImage: "bell.slash") }
                    }
                }
            }
            if item.actionType == .reply {
                Section("返信") {
                    Text("元文章").font(.headline)
                    Text(item.rawOCRText.isEmpty ? item.note : item.rawOCRText).textSelection(.enabled)
                    LabeledContent("AI返信案", value: "OFF・未接続")
                    Text("クラウドAIは接続されていません。元文章をコピーして、返信するアプリで編集できます。")
                        .font(.footnote).foregroundStyle(.secondary)
                    Button {
                        UIPasteboard.general.setItems([["public.utf8-plain-text": item.rawOCRText.isEmpty ? item.note : item.rawOCRText]],
                            options: [.localOnly: true, .expirationDate: Date().addingTimeInterval(300)])
                        copied = true
                    } label: { Label(copied ? "コピーしました" : "元文章をコピー", systemImage: "doc.on.doc") }
                }
            }
            if !item.rawOCRText.isEmpty {
                Section { DisclosureGroup("読み取った原文") { Text(item.rawOCRText).textSelection(.enabled) } }
            }
        }
        .navigationTitle("詳細").navigationBarTitleDisplayMode(.inline)
        .sheet(isPresented: $showingSnooze) { SnoozeSheet(item: item) }
        .sheet(isPresented: $showingEdit) { NavigationStack { EditItemView(item: item) } }
        .sheet(isPresented: $showingLocation) { NavigationStack { LocationReminderView(item: item) } }
    }
    private var hasExtractedFields: Bool {
        [item.extractedProductName, item.extractedPrice, item.extractedPlace, item.extractedAddress,
         item.extractedPhone, item.extractedEmail, item.extractedOrderNumber, item.extractedReservationNumber]
            .contains { $0 != nil } || item.extractedReturnDeadline != nil
    }
    @ViewBuilder private func field(_ name: String, _ value: String?) -> some View {
        if let value { LabeledContent(name) { Text(value).textSelection(.enabled) } }
    }
    private func openMap() {
        var components = URLComponents(string: "https://maps.apple.com/")
        components?.queryItems = [URLQueryItem(name: "q", value: item.extractedAddress ?? item.extractedPlace)]
        if let url = components?.url { openURL(url) }
    }
}
