import EventKit
import Foundation

@MainActor
final class CalendarService {
    private let store = EKEventStore()
    func add(_ item: InboxItem) async throws {
        guard let date = item.dueDate else { return }
        guard try await store.requestWriteOnlyAccessToEvents() else {
            throw NSError(domain: "Calendar", code: 1,
                userInfo: [NSLocalizedDescriptionKey: "カレンダーへの追加を許可してください。項目は箱に保存されています。"])
        }
        let event = EKEvent(eventStore: store)
        event.title = item.title
        event.notes = item.note
        event.location = item.extractedAddress ?? item.extractedPlace
        event.startDate = date
        event.endDate = date.addingTimeInterval(3600)
        event.calendar = store.defaultCalendarForNewEvents
        try store.save(event, span: .thisEvent)
    }
}
