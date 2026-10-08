import Foundation
import SwiftData

@MainActor
enum WidgetStoreQueries {
    static func timeline(context: ModelContext, now: Date = Date(), calendar: Calendar = .current) throws -> [WidgetSnapshot] {
        // Precompute bounded future entries so deadlines can change the displayed
        // count even if the app stays closed and WidgetKit delays a reload.
        let end = now.addingTimeInterval(3600)
        let completed = ItemStatus.completed.rawValue
        let archived = ItemStatus.archived.rawValue
        let future = Date.distantFuture
        let pending = #Predicate<InboxItem> {
            $0.statusRaw != completed && $0.statusRaw != archived &&
            ($0.dueDate ?? future) >= now && ($0.dueDate ?? future) < end
        }
        var query = FetchDescriptor(predicate: pending, sortBy: [SortDescriptor(\InboxItem.dueDate)])
        query.fetchLimit = 12
        query.propertiesToFetch = [\InboxItem.dueDate]
        var dates = [now, end]
        dates += try context.fetch(query).compactMap { $0.dueDate.map { min($0.addingTimeInterval(1), end) } }
        if let tomorrow = calendar.date(byAdding: .day, value: 1, to: calendar.startOfDay(for: now)),
           tomorrow > now && tomorrow < end { dates.append(tomorrow) }
        return try Set(dates).sorted().map { try snapshot(context: context, now: $0, calendar: calendar) }
    }

    static func snapshot(context: ModelContext, now: Date = Date(), calendar: Calendar = .current) throws -> WidgetSnapshot {
        let completed = ItemStatus.completed.rawValue
        let archived = ItemStatus.archived.rawValue
        let future = Date.distantFuture
        let start = calendar.startOfDay(for: now)
        let end = calendar.date(byAdding: .day, value: 1, to: start) ?? start.addingTimeInterval(86400)
        let open = #Predicate<InboxItem> { $0.statusRaw != completed && $0.statusRaw != archived }
        let overdue = #Predicate<InboxItem> {
            $0.statusRaw != completed && $0.statusRaw != archived && ($0.dueDate ?? future) < now
        }
        let today = #Predicate<InboxItem> {
            $0.statusRaw != completed && $0.statusRaw != archived && ($0.dueDate ?? future) >= start && ($0.dueDate ?? future) < end
        }
        let dated = #Predicate<InboxItem> {
            $0.statusRaw != completed && $0.statusRaw != archived && $0.dueDate != nil
        }
        var todayQuery = FetchDescriptor(predicate: today, sortBy: [SortDescriptor(\InboxItem.dueDate)])
        todayQuery.fetchLimit = 3
        todayQuery.propertiesToFetch = [\InboxItem.id, \InboxItem.title, \InboxItem.dueDate]
        var nextQuery = FetchDescriptor(predicate: dated, sortBy: [SortDescriptor(\InboxItem.dueDate)])
        nextQuery.fetchLimit = 1
        nextQuery.propertiesToFetch = [\InboxItem.id, \InboxItem.title, \InboxItem.dueDate]
        func summary(_ item: InboxItem) -> WidgetItem {
            WidgetItem(id: item.id, title: String(item.title.prefix(160)), dueDate: item.dueDate)
        }
        return WidgetSnapshot(generatedAt: now,
            openCount: try context.fetchCount(FetchDescriptor(predicate: open)),
            overdueCount: try context.fetchCount(FetchDescriptor(predicate: overdue)),
            today: try context.fetch(todayQuery).map(summary),
            next: try context.fetch(nextQuery).first.map(summary))
    }
}
