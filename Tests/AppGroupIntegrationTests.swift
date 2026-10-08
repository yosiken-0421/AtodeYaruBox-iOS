import XCTest
import SwiftData
@testable import AtodeYaruBox

final class AppGroupIntegrationTests: XCTestCase {
    @MainActor func testExistingReceiverSeesCompletedStateAfterReload() throws {
        let writer = try SharedStore.container(requireGroup: true)
        writer.mainContext.autosaveEnabled = false
        let item = InboxItem(title: "QA reload " + UUID().uuidString, sourceType: .text)
        let writerRepository = InboxRepository(context: writer.mainContext)
        try writerRepository.insert(item)
        defer {
            writer.mainContext.delete(item)
            try? writer.mainContext.save()
        }

        let receiver = try SharedStore.container(requireGroup: true)
        let receiverRepository = InboxRepository(context: receiver.mainContext)
        let initial = try XCTUnwrap(receiverRepository.find(item.id))
        XCTAssertTrue(initial.status.isOpen)
        try writerRepository.complete(item)
        // Use the production refresh path before fetching; a fetch alone may
        // retain registered SwiftData objects with another context's old values.
        try receiverRepository.refreshExternalChanges()
        let reloaded = try XCTUnwrap(receiverRepository.all().first { $0.id == item.id })
        XCTAssertTrue(initial === reloaded)
        XCTAssertEqual(reloaded.status, .completed)
        XCTAssertNotNil(reloaded.completedAt)
    }

    @MainActor func testSignedHostGroupStorePersistsAcrossIndependentContainers() throws {
        let root = try SharedStore.directory(requireGroup: true)
        XCTAssertTrue(root.isFileURL)
        let writer = try SharedStore.container(requireGroup: true)
        writer.mainContext.autosaveEnabled = false
        let item = InboxItem(title: "QA group " + UUID().uuidString, sourceType: .text)
        let id = item.id
        let writerRepository = InboxRepository(context: writer.mainContext)
        try writerRepository.insert(item)
        defer {
            // Only this test's UUID, in the ephemeral Simulator's group store.
            writer.mainContext.delete(item)
            try? writer.mainContext.save()
        }
        let reader = try SharedStore.container(requireGroup: true)
        let persisted = try XCTUnwrap(InboxRepository(context: reader.mainContext).find(id))
        XCTAssertEqual(persisted.title, item.title)
        XCTAssertEqual(persisted.id, id)
        XCTAssertEqual(persisted.status, item.status)
    }
}
