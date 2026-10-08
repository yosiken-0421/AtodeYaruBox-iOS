import Foundation
import AppIntents

struct SaveToBoxIntent: AppIntent {
    static var title: LocalizedStringResource = "あとでやる箱へ保存"
    static var description = IntentDescription("メモやWebページを箱に保存します。外部への送信は行いません。")
    @Parameter(title: "タイトル") var title: String
    @Parameter(title: "メモ") var note: String?
    @Parameter(title: "URL") var url: String?

    @MainActor func perform() async throws -> some IntentResult & ProvidesDialog {
        guard !title.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { throw AppError.emptyTitle }
        if let url, URLValidator.webURL(url) == nil { throw AppError.invalidURL }
        let container = try SharedStore.container(requireGroup: true)
        let repository = InboxRepository(context: container.mainContext)
        let item = InboxItem(title: title, note: note ?? "", sourceType: url == nil ? .memo : .url,
                             actionType: ClassificationService.classify(title + "\n" + (note ?? "")).action)
        item.sourceURL = url
        try repository.insert(item)
        try? WidgetSnapshotService.write(items: repository.all())
        return .result(dialog: "箱に保存しました。")
    }
}

struct OpenTodayIntent: AppIntent {
    static var title: LocalizedStringResource = "今日を開く"
    static var openAppWhenRun = true
    @MainActor func perform() async throws -> some IntentResult {
        RouteStore.request("today")
        return .result()
    }
}

struct NewMemoIntent: AppIntent {
    static var title: LocalizedStringResource = "新規メモ"
    static var openAppWhenRun = true
    @MainActor func perform() async throws -> some IntentResult {
        RouteStore.request("new")
        return .result()
    }
}

struct NextItemIntent: AppIntent {
    static var title: LocalizedStringResource = "次の項目"
    @MainActor func perform() async throws -> some IntentResult & ProvidesDialog {
        let container = try SharedStore.container(requireGroup: true)
        let next = try InboxRepository(context: container.mainContext).all().filter { $0.status.isOpen }
            .sorted { ($0.dueDate ?? .distantFuture) < ($1.dueDate ?? .distantFuture) }.first
        if let next { return .result(dialog: "次の項目は「\(next.title)」です。") }
        return .result(dialog: "未完了の項目はありません。")
    }
}

struct CompleteItemIntent: AppIntent {
    static var title: LocalizedStringResource = "項目を完了"
    @Parameter(title: "項目ID") var itemID: String
    init() {}
    init(itemID: String) { self.itemID = itemID }
    @MainActor func perform() async throws -> some IntentResult {
        guard let id = UUID(uuidString: itemID) else { throw AppError.staleItem }
        let container = try SharedStore.container(requireGroup: true)
        let repository = InboxRepository(context: container.mainContext)
        guard let item = try repository.find(id) else { throw AppError.staleItem }
        try repository.complete(item)
        let items = try repository.all()
        try? WidgetSnapshotService.write(items: items)
        try await NotificationScheduler().reconcile(items: items)
        return .result()
    }
}
