import SwiftUI
import SwiftData
import WidgetKit
import AppIntents

struct BoxEntry: TimelineEntry, Sendable {
    var date: Date
    var snapshot: WidgetSnapshot
    var notice: String? = nil
}

struct BoxProvider: TimelineProvider {
    func placeholder(in context: Context) -> BoxEntry {
        let now = Date()
        return BoxEntry(date: now, snapshot: WidgetSnapshot(generatedAt: now, openCount: 3, overdueCount: 1,
            today: [WidgetItem(id: UUID(), title: "今日のあとでやること", dueDate: now)], next: nil))
    }

    func getSnapshot(in context: Context, completion: @escaping @Sendable (BoxEntry) -> Void) {
        Task { @MainActor in
            let now = Date()
            do {
                let container = try SharedStore.container(requireGroup: true)
                let snapshot = try WidgetStoreQueries.snapshot(context: ModelContext(container), now: now)
                completion(BoxEntry(date: now, snapshot: snapshot))
            } catch {
                completion(BoxEntry(date: now, snapshot: .empty, notice: "箱を開いて確認してください"))
            }
        }
    }

    func getTimeline(in context: Context, completion: @escaping @Sendable (Timeline<BoxEntry>) -> Void) {
        Task { @MainActor in
            let now = Date()
            do {
                let container = try SharedStore.container(requireGroup: true)
                let snapshots = try WidgetStoreQueries.timeline(context: ModelContext(container), now: now)
                let entries = snapshots.map { BoxEntry(date: $0.generatedAt, snapshot: $0) }
                completion(Timeline(entries: entries, policy: .atEnd))
            } catch {
                let entry = BoxEntry(date: now, snapshot: .empty, notice: "箱を開いて確認してください")
                completion(Timeline(entries: [entry], policy: .after(now.addingTimeInterval(3600))))
            }
        }
    }
}

struct HomeBoxWidgetView: View {
    var entry: BoxEntry
    @Environment(\.widgetFamily) private var family
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Label("あとでやる箱", systemImage: "tray").font(.headline)
            if let notice = entry.notice {
                Label(notice, systemImage: "exclamationmark.triangle").font(.subheadline)
                    .fixedSize(horizontal: false, vertical: true)
            } else {
            if entry.snapshot.overdueCount > 0 {
                Label("期限切れ \(entry.snapshot.overdueCount)件", systemImage: "exclamationmark.triangle").foregroundStyle(.red)
            } else { Text("未完了 \(entry.snapshot.openCount)件").font(.subheadline) }
            if let item = entry.snapshot.today.first ?? entry.snapshot.next {
                Text(item.title).font(.subheadline).lineLimit(family == .systemSmall ? 2 : 3)
                if let date = item.dueDate { Text(date, format: .dateTime.month().day().hour().minute()).font(.caption) }
                if family == .systemMedium {
                    Button(intent: CompleteItemIntent(itemID: item.id.uuidString)) { Label("完了", systemImage: "checkmark") }
                        .buttonStyle(.bordered).tint(.boxAccent)
                }
            } else { Text("今日の項目はありません").font(.subheadline) }
            }
        }
        .containerBackground(.fill.tertiary, for: .widget)
        .widgetURL(URL(string: "atodeyarubox://today"))
    }
}

struct LockBoxWidgetView: View {
    var entry: BoxEntry
    @Environment(\.widgetFamily) private var family
    var body: some View {
        Group {
            if let notice = entry.notice {
                Group {
                    if family == .accessoryCircular {
                        VStack { Image(systemName: "exclamationmark.triangle"); Text("確認") }
                    } else {
                        Label("箱で確認", systemImage: "exclamationmark.triangle")
                    }
                }.accessibilityLabel(notice)
            } else {
            if family == .accessoryCircular {
                VStack { Image(systemName: "tray"); Text("\(entry.snapshot.openCount)") }
                    .accessibilityLabel("未完了 \(entry.snapshot.openCount)件")
            } else {
                VStack(alignment: .leading) {
                    Label("未完了 \(entry.snapshot.openCount)件", systemImage: "tray")
                    if let date = entry.snapshot.next?.dueDate {
                        Text(date, format: .dateTime.month().day().hour().minute())
                    } else { Text("次の期限は未設定") }
                }
            }
            }
        }.containerBackground(.fill.tertiary, for: .widget)
            .widgetURL(URL(string: "atodeyarubox://today"))
    }
}

struct HomeBoxWidget: Widget {
    var body: some WidgetConfiguration {
        StaticConfiguration(kind: "HomeBox", provider: BoxProvider()) { HomeBoxWidgetView(entry: $0) }
            .configurationDisplayName("今日の箱").description("期限切れ、今日の項目、次の予定を表示します。")
            .supportedFamilies([.systemSmall, .systemMedium])
    }
}
struct LockBoxWidget: Widget {
    var body: some WidgetConfiguration {
        StaticConfiguration(kind: "LockBox", provider: BoxProvider()) { LockBoxWidgetView(entry: $0) }
            .configurationDisplayName("未完了と次の期限").description("ロック画面で件数と次の期限を確認できます。")
            .supportedFamilies([.accessoryCircular, .accessoryRectangular])
    }
}

@main
struct BoxWidgets: WidgetBundle {
    var body: some Widget { HomeBoxWidget(); LockBoxWidget() }
}
