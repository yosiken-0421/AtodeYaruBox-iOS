import XCTest
import SwiftData
@testable import AtodeYaruBox

final class NotificationActionIntegrationTests: XCTestCase {
    @MainActor func testOldNotificationCannotReopenItemCompletedInAnotherContainer() throws {
        let writer = try SharedStore.container(requireGroup: true)
        writer.mainContext.autosaveEnabled = false
        let writerRepository = InboxRepository(context: writer.mainContext)
        let item = InboxItem(title: "QA completed action " + UUID().uuidString, dueDate: Date().addingTimeInterval(3600))
        try writerRepository.insert(item)
        defer { writer.mainContext.delete(item); try? writer.mainContext.save() }
        let receiver = try SharedStore.container(requireGroup: true)
        receiver.mainContext.autosaveEnabled = false
        let receiverRepository = InboxRepository(context: receiver.mainContext)
        let oldObject = try XCTUnwrap(receiverRepository.find(item.id))
        XCTAssertTrue(oldObject.status.isOpen)
        let completedAt = Date(timeIntervalSince1970: floor(Date().timeIntervalSince1970) + 1)
        try writerRepository.complete(item, now: completedAt)
        let changed = try NotificationActionService.apply(identifier: NotificationScheduler.hourAction,
            itemID: item.id, repository: receiverRepository, now: completedAt.addingTimeInterval(1))
        XCTAssertFalse(changed)
        XCTAssertEqual(oldObject.status, .completed)
        XCTAssertEqual(oldObject.completedAt, completedAt)
        let verification = try SharedStore.container(requireGroup: true)
        let saved = try XCTUnwrap(InboxRepository(context: verification.mainContext).find(item.id))
        XCTAssertEqual(saved.status, .completed)
        XCTAssertEqual(saved.completedAt, completedAt)
        XCTAssertEqual(saved.dueDate, item.dueDate)
    }

    @MainActor func testHourThenCompleteUsesFreshSavedStateAndCompletionIsIdempotent() throws {
        let writer = try SharedStore.container(requireGroup: true)
        writer.mainContext.autosaveEnabled = false
        let item = InboxItem(title: "QA active action " + UUID().uuidString)
        try InboxRepository(context: writer.mainContext).insert(item)
        defer { writer.mainContext.delete(item); try? writer.mainContext.save() }
        let receiver = try SharedStore.container(requireGroup: true)
        receiver.mainContext.autosaveEnabled = false
        let repository = InboxRepository(context: receiver.mainContext)
        let now = Date(timeIntervalSince1970: floor(Date().timeIntervalSince1970) + 1)
        XCTAssertTrue(try NotificationActionService.apply(identifier: NotificationScheduler.hourAction,
            itemID: item.id, repository: repository, now: now))
        let verification = try SharedStore.container(requireGroup: true)
        let saved = try XCTUnwrap(InboxRepository(context: verification.mainContext).find(item.id))
        XCTAssertEqual(saved.status, .snoozed)
        XCTAssertEqual(saved.dueDate, now.addingTimeInterval(3600))
        XCTAssertTrue(try NotificationActionService.apply(identifier: NotificationScheduler.completeAction,
            itemID: item.id, repository: repository, now: now.addingTimeInterval(2)))
        let completed = try XCTUnwrap(repository.find(item.id))
        let firstCompletion = completed.completedAt
        XCTAssertFalse(try NotificationActionService.apply(identifier: NotificationScheduler.completeAction,
            itemID: item.id, repository: repository, now: now.addingTimeInterval(3)))
        XCTAssertEqual(completed.completedAt, firstCompletion)
        XCTAssertFalse(try NotificationActionService.apply(identifier: NotificationScheduler.tomorrowAction,
            itemID: item.id, repository: repository, now: now.addingTimeInterval(4)))
        XCTAssertEqual(completed.status, .completed)
    }
}
