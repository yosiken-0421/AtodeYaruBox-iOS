import Foundation
import WidgetKit

struct WidgetItem: Codable, Sendable {
    var id: UUID
    var title: String
    var dueDate: Date?
}

struct WidgetSnapshot: Codable, Sendable {
    var generatedAt: Date
    var openCount: Int
    var overdueCount: Int
    var today: [WidgetItem]
    var next: WidgetItem?
    static let empty = WidgetSnapshot(generatedAt: Date(), openCount: 0, overdueCount: 0, today: [], next: nil)
}

@MainActor
enum WidgetSnapshotService {
    static func write(items: [InboxItem], now: Date = Date(), calendar: Calendar = .current) throws {
        let open = items.filter { $0.status.isOpen }
        let ordered = open.sorted { ($0.dueDate ?? .distantFuture) < ($1.dueDate ?? .distantFuture) }
        func widget(_ item: InboxItem) -> WidgetItem { WidgetItem(id: item.id, title: item.title, dueDate: item.dueDate) }
        let snapshot = WidgetSnapshot(generatedAt: now, openCount: open.count,
            overdueCount: open.filter { ($0.dueDate ?? .distantFuture) < now }.count,
            today: ordered.filter { $0.dueDate.map { calendar.isDate($0, inSameDayAs: now) } ?? false }.prefix(3).map(widget),
            next: ordered.first.map(widget))
        let path = try SharedStore.directory(requireGroup: true).appendingPathComponent("Widget.json")
        try JSONEncoder().encode(snapshot).write(to: path, options: [.atomic, .completeFileProtectionUntilFirstUserAuthentication])
        WidgetCenter.shared.reloadAllTimelines()
    }
    // Reading immutable JSON does not touch SwiftData or any main-thread state.
    nonisolated static func read() -> WidgetSnapshot {
        guard let root = try? SharedStore.directory(requireGroup: true),
              let data = try? Data(contentsOf: root.appendingPathComponent("Widget.json")),
              let snapshot = try? JSONDecoder().decode(WidgetSnapshot.self, from: data) else { return .empty }
        return snapshot
    }
}
