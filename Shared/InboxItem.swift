import Foundation
import SwiftData

@Model
final class InboxItem {
    var id: UUID = UUID()
    var createdAt: Date = Date()
    var updatedAt: Date = Date()
    var title: String = ""
    var note: String = ""
    var sourceTypeRaw: String = SourceType.memo.rawValue
    var sourceURL: String?
    var localAssetPath: String?
    var thumbnailPath: String?
    var rawOCRText: String = ""
    var actionTypeRaw: String = ActionType.memo.rawValue
    var confidence: Double = 1
    var dueDate: Date?
    var reminderModeRaw: String = ReminderMode.normal.rawValue
    var reminderInterval: TimeInterval = 3600
    var locationReminderData: Data?
    var extractedPrice: String?
    var extractedPlace: String?
    var extractedProductName: String?
    var extractedAddress: String?
    var extractedPhone: String?
    var extractedEmail: String?
    var extractedOrderNumber: String?
    var extractedReservationNumber: String?
    var extractedReturnDeadline: Date?
    var statusRaw: String = ItemStatus.inbox.rawValue
    var completedAt: Date?
    var tags: [String] = []
    var calendarAddedAt: Date?

    init(title: String, note: String = "", sourceType: SourceType = .memo,
         actionType: ActionType = .memo, dueDate: Date? = nil, now: Date = Date()) {
        self.title = title.trimmingCharacters(in: .whitespacesAndNewlines)
        self.note = note
        self.sourceTypeRaw = sourceType.rawValue
        self.actionTypeRaw = actionType.rawValue
        self.dueDate = dueDate
        self.createdAt = now
        self.updatedAt = now
        self.statusRaw = ItemStatus.active.rawValue
    }

    var status: ItemStatus {
        get { ItemStatus(rawValue: statusRaw) ?? .inbox }
        set { statusRaw = newValue.rawValue }
    }
    var actionType: ActionType {
        get { ActionType(rawValue: actionTypeRaw) ?? .other }
        set { actionTypeRaw = newValue.rawValue }
    }
    var sourceType: SourceType {
        get { SourceType(rawValue: sourceTypeRaw) ?? .file }
        set { sourceTypeRaw = newValue.rawValue }
    }
    var reminderMode: ReminderMode {
        get { ReminderMode(rawValue: reminderModeRaw) ?? .normal }
        set { reminderModeRaw = newValue.rawValue }
    }
    var locationReminder: LocationReminder? {
        get {
            guard let data = locationReminderData else { return nil }
            return try? JSONDecoder().decode(LocationReminder.self, from: data)
        }
        set { locationReminderData = newValue.flatMap { try? JSONEncoder().encode($0) } }
    }
    func complete(now: Date = Date()) {
        guard status.isOpen else { return }
        status = .completed
        completedAt = now
        updatedAt = now
    }
    func snooze(until date: Date, now: Date = Date()) {
        guard status.isOpen, date > now else { return }
        dueDate = date
        status = .snoozed
        completedAt = nil
        updatedAt = now
    }
    func reopen(now: Date = Date()) {
        status = .active
        completedAt = nil
        updatedAt = now
    }

    func copyPersistedState(from source: InboxItem) {
        createdAt = source.createdAt; updatedAt = source.updatedAt
        title = source.title; note = source.note; sourceTypeRaw = source.sourceTypeRaw
        sourceURL = source.sourceURL; localAssetPath = source.localAssetPath; thumbnailPath = source.thumbnailPath
        rawOCRText = source.rawOCRText; actionTypeRaw = source.actionTypeRaw; confidence = source.confidence
        dueDate = source.dueDate; reminderModeRaw = source.reminderModeRaw; reminderInterval = source.reminderInterval
        locationReminderData = source.locationReminderData; extractedPrice = source.extractedPrice
        extractedPlace = source.extractedPlace; extractedProductName = source.extractedProductName
        extractedAddress = source.extractedAddress; extractedPhone = source.extractedPhone; extractedEmail = source.extractedEmail
        extractedOrderNumber = source.extractedOrderNumber; extractedReservationNumber = source.extractedReservationNumber
        extractedReturnDeadline = source.extractedReturnDeadline; statusRaw = source.statusRaw; completedAt = source.completedAt
        tags = source.tags; calendarAddedAt = source.calendarAddedAt
    }
}
