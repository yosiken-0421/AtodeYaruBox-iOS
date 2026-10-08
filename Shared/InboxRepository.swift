import Foundation
import SwiftData

@MainActor
final class InboxRepository {
    let context: ModelContext
    init(context: ModelContext) { self.context = context }

    func all() throws -> [InboxItem] {
        try context.fetch(FetchDescriptor<InboxItem>(sortBy: [SortDescriptor(\InboxItem.createdAt, order: .reverse)]))
    }
    func find(_ id: UUID) throws -> InboxItem? {
        var query = FetchDescriptor<InboxItem>(predicate: #Predicate { $0.id == id })
        query.fetchLimit = 1
        return try context.fetch(query).first
    }
    func insert(_ item: InboxItem) throws {
        guard !item.title.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { throw AppError.emptyTitle }
        context.insert(item)
        try save()
    }
    func complete(_ item: InboxItem, now: Date = Date()) throws {
        item.complete(now: now)
        try save()
        NotificationScheduler.cancel(itemID: item.id)
    }
    func snooze(_ item: InboxItem, until date: Date, now: Date = Date()) throws {
        guard date > now else { throw AppError.invalidSnoozeDate }
        guard item.status.isOpen else { throw AppError.staleItem }
        item.snooze(until: date, now: now)
        try save()
    }
    func reopen(_ item: InboxItem) throws { item.reopen(); try save() }
    func update(_ item: InboxItem, changes: (InboxItem) -> Void) throws {
        changes(item)
        item.updatedAt = Date()
        try save()
    }
    func save() throws {
        do { try context.save() } catch { context.rollback(); throw error }
    }

    func refreshExternalChanges() throws {
        // Each extension has its own process/context. Refresh already registered objects
        // before rebuilding widgets and notifications, including items just completed there.
        guard !context.hasChanges else { return }
        let freshContext = ModelContext(context.container)
        let freshItems = try freshContext.fetch(FetchDescriptor<InboxItem>())
        for source in freshItems {
            if let existing = try find(source.id), source.updatedAt > existing.updatedAt {
                existing.copyPersistedState(from: source)
            }
        }
        if context.hasChanges { try save() }
    }
}
