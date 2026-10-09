import XCTest

final class ExternalInputFlowTests: XCTestCase {
    override func setUpWithError() throws {
        continueAfterFailure = false
        executionTimeAllowance = 240
    }

    @MainActor private func host() -> XCUIApplication {
        let app = XCUIApplication()
        // Persistent App Group and real side effects are necessary for Safari.
        app.launchArguments = ["--qa-light", "-UIPreferredContentSizeCategoryName", "UICTContentSizeCategoryL"]
        app.launch()
        if app.buttons["onboardingSkip"].waitForExistence(timeout: 5) { app.buttons["onboardingSkip"].tap() }
        XCTAssertTrue(app.tabBars.buttons["箱"].waitForExistence(timeout: 10))
        return app
    }

    @MainActor private func search(_ app: XCUIApplication, query: String) {
        app.tabBars.buttons["探す"].tap()
        let field = app.textFields["searchField"]
        XCTAssertTrue(field.waitForExistence(timeout: 5))
        field.tap()
        if let old = field.value as? String, old != field.placeholderValue {
            field.typeText(String(repeating: XCUIKeyboardKey.delete.rawValue, count: old.count))
        }
        field.typeText(query)
        app.buttons["searchSubmitButton"].tap()
        XCTAssertEqual(app.keyboards.count, 0)
    }

    @MainActor private func attachment(_ app: XCUIApplication, name: String) {
        let image = XCTAttachment(screenshot: app.screenshot())
        image.name = name
        image.lifetime = .keepAlways
        add(image)
    }

    @MainActor private func reveal(_ element: XCUIElement, in app: XCUIApplication) {
        for _ in 0..<8 {
            if element.exists && element.isHittable { return }
            app.swipeUp()
        }
        XCTAssertTrue(element.exists && element.isHittable, "The control must be reachable by ordinary scrolling")
    }

    @MainActor func testPhotosPickerReadsSelectedScreenshotAndSearchesOCR() throws {
        let app = host()
        app.buttons["addButton"].tap()
        let choose = app.buttons["写真を選ぶ"]
        XCTAssertTrue(choose.waitForExistence(timeout: 5))
        choose.tap()
        attachment(app, name: "ActualPhotosPickerBeforeSelection")
        // Let the system library finish its initial load before querying thumbnails.
        let photoReady = NSPredicate { _, _ in self.photoCandidate(app) != nil }
        let ready = XCTNSPredicateExpectation(predicate: photoReady, object: app)
        let readyResult = XCTWaiter.wait(for: [ready], timeout: 30)
        XCTAssertEqual(readyResult, .completed, "PHOTO_PICKER_NO_VISIBLE_CELL; " + controls(app))
        let photo = try XCTUnwrap(photoCandidate(app))
        let selectedLabel = String(photo.label.prefix(120))
        attachment(app, name: "ActualPhotosPicker")
        if photo.isHittable { photo.tap() }
        else { photo.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.5)).tap() }
        let original = app.buttons["読み取った原文"]
        // OCR can add an attachment above this disclosure; ordinary scrolling
        // must still reach the result in the actual compose form.
        let title = app.descendants(matching: .any).matching(identifier: "titleField").firstMatch
        let recognized = NSPredicate(format: "value CONTAINS %@", "Return deadline")
        let ocrReady = XCTNSPredicateExpectation(predicate: recognized, object: title)
        let ocrResult = XCTWaiter.wait(for: [ocrReady], timeout: 30)
        XCTAssertEqual(ocrResult, .completed,
            "PHOTO_OCR_RESULT_NOT_VISIBLE; selected=" + selectedLabel + "; title=" + String(describing: title.value) + "; " + controls(app))
        reveal(original, in: app)
        original.tap()
        XCTAssertTrue(app.staticTexts.containing(NSPredicate(format: "label CONTAINS %@", "PHOTO123")).firstMatch.exists)
        let date = app.switches["hasDateToggle"]
        reveal(date, in: app)
        XCTAssertEqual(date.value as? String, "1", "OCR must propose the date printed on the selected fixture")
        date.tap() // This flow verifies photo input; notification permission is tested separately.
        if date.value as? String == "1" {
            // A wide SwiftUI switch row can expose a label-inclusive frame.
            // Tap the actual trailing switch if the row's center was just a label.
            date.coordinate(withNormalizedOffset: CGVector(dx: 0.9, dy: 0.5)).tap()
        }
        XCTAssertEqual(date.value as? String, "0", "Turning off the detected date must keep it off")
        app.buttons["toolbarSaveButton"].tap()
        search(app, query: "PHOTO123")
        let saved = app.staticTexts.containing(NSPredicate(format: "label CONTAINS %@", "Return deadline")).firstMatch
        XCTAssertTrue(saved.waitForExistence(timeout: 10))
        saved.tap()
        XCTAssertTrue(app.staticTexts["返品"].waitForExistence(timeout: 5), "The selected screenshot must retain its detected action after saving")
        attachment(app, name: "PhotoOCRSavedAndSearchable")
    }

    @MainActor private func safariPage() throws -> XCUIApplication {
        let app = host()
        app.terminate()
        let address = try XCTUnwrap(ProcessInfo.processInfo.environment["ATODE_QA_LOOPBACK_URL"])
        let components = try XCTUnwrap(URLComponents(string: address))
        XCTAssertEqual(components.scheme, "http")
        XCTAssertEqual(components.host, "127.0.0.1")
        let safari = XCUIApplication(bundleIdentifier: "com.apple.mobilesafari")
        safari.launch()
        for label in ["Continue", "続ける", "Start Browsing", "ブラウズを開始"] {
            if safari.buttons[label].waitForExistence(timeout: 2) { safari.buttons[label].tap() }
        }
        var field = safari.textFields.matching(NSPredicate(format: "label CONTAINS[c] %@ OR label CONTAINS %@", "Address", "アドレス")).firstMatch
        if !field.exists {
            let addressButton = safari.buttons.matching(NSPredicate(format: "label CONTAINS[c] %@ OR label CONTAINS %@", "Address", "アドレス")).firstMatch
            XCTAssertTrue(addressButton.waitForExistence(timeout: 5), "Safari address control not found")
            addressButton.tap()
            field = safari.textFields.firstMatch
        }
        XCTAssertTrue(field.waitForExistence(timeout: 5))
        field.tap()
        if let old = field.value as? String, old != field.placeholderValue {
            field.typeText(String(repeating: XCUIKeyboardKey.delete.rawValue, count: old.count))
        }
        field.typeText(address + "\n")
        XCTAssertTrue(safari.webViews.staticTexts["ATODE-SAFARI-FIXTURE"].waitForExistence(timeout: 15))
        return safari
    }

    @MainActor private func openShare(_ safari: XCUIApplication) {
        var menuLabel = "direct share"
        if shareCandidate(safari) == nil {
            let menu = safari.buttons.matching(NSPredicate(format: "label BEGINSWITH[c] %@ OR label BEGINSWITH %@ OR label BEGINSWITH[c] %@ OR label BEGINSWITH %@", "More", "その他", "Page Menu", "ページメニュー")).firstMatch
            XCTAssertTrue(menu.waitForExistence(timeout: 5), "SAFARI_PAGE_MENU_NOT_FOUND; " + controls(safari))
            menuLabel = String(menu.label.prefix(120))
            menu.tap()
        }
        let ready = XCTNSPredicateExpectation(predicate: NSPredicate { _, _ in self.shareCandidate(safari) != nil }, object: safari)
        XCTAssertEqual(XCTWaiter.wait(for: [ready], timeout: 8), .completed,
            "SAFARI_SHARE_ITEM_NOT_FOUND; menu=" + menuLabel + "; " + controls(safari))
        guard let share = shareCandidate(safari) else { return }
        share.tap()
        let targetPredicate = NSPredicate(format: "label BEGINSWITH %@", "あとでやる箱")
        let morePredicate = NSPredicate(format: "label BEGINSWITH[c] %@ OR label BEGINSWITH %@", "More", "その他")
        let sheetReady = XCTNSPredicateExpectation(predicate: NSPredicate { _, _ in
            self.activityCandidate(safari, matching: targetPredicate) != nil
                || self.activityCandidate(safari, matching: morePredicate) != nil
        }, object: safari)
        let sheetResult = XCTWaiter.wait(for: [sheetReady], timeout: 8)
        attachment(safari, name: "ActualSafariShareSheetBeforeSelection")
        XCTAssertEqual(sheetResult, .completed, "SAFARI_ACTIVITY_SHEET_NOT_READY; " + controls(safari))
        if activityCandidate(safari, matching: targetPredicate) == nil {
            let more = activityCandidate(safari, matching: morePredicate)
            XCTAssertNotNil(more, "SHARE_EXTENSION_AND_MORE_NOT_VISIBLE; " + controls(safari))
            guard let more else { return }
            more.tap()
        }
        let targetReady = XCTNSPredicateExpectation(predicate: NSPredicate { _, _ in
            self.activityCandidate(safari, matching: targetPredicate) != nil
        }, object: safari)
        let targetResult = XCTWaiter.wait(for: [targetReady], timeout: 10)
        attachment(safari, name: "ActualSafariShareActivities")
        XCTAssertEqual(targetResult, .completed, "INSTALLED_SHARE_EXTENSION_NOT_AVAILABLE; " + controls(safari))
        guard let target = activityCandidate(safari, matching: targetPredicate) else { return }
        target.tap()
        XCTAssertTrue(safari.buttons["箱に保存"].waitForExistence(timeout: 15))
        attachment(safari, name: "ActualSafariShareExtension")
    }

    @MainActor func testSafariSharesURLAndHostShowsReviewedInbox() throws {
        let safari = try safariPage()
        openShare(safari)
        let title = "SafariQA-" + UUID().uuidString.prefix(8)
        let field = safari.descendants(matching: .any).matching(identifier: "sharedTitleField").firstMatch
        XCTAssertTrue(field.waitForExistence(timeout: 5))
        field.tap()
        if let old = field.value as? String { field.typeText(String(repeating: XCUIKeyboardKey.delete.rawValue, count: old.count)) }
        field.typeText(title)
        XCTAssertEqual(field.value as? String, title, "The edited title must be reflected before saving")
        attachment(safari, name: "SafariSharedTitleReadyToSave")
        let save = safari.buttons["shareToolbarSaveButton"]
        XCTAssertTrue(save.isEnabled && save.isHittable)
        save.tap()
        let finished = XCTNSPredicateExpectation(predicate: NSPredicate(format: "exists == false"), object: save)
        let saveResult = XCTWaiter.wait(for: [finished], timeout: 10)
        attachment(safari, name: "SafariAfterSave")
        XCTAssertEqual(saveResult, .completed, "SHARE_SAVE_DID_NOT_FINISH; " + controls(safari))
        let app = host()
        search(app, query: title)
        let saved = app.staticTexts.containing(NSPredicate(format: "label CONTAINS %@", title)).firstMatch
        let imported = saved.waitForExistence(timeout: 10)
        attachment(app, name: "SafariSharedItemSearchResult")
        XCTAssertTrue(imported, "SHARED_TITLE_NOT_SEARCHABLE; " + controls(app))
        saved.tap()
        XCTAssertTrue(app.buttons["確認しました"].waitForExistence(timeout: 5))
        let address = try XCTUnwrap(ProcessInfo.processInfo.environment["ATODE_QA_LOOPBACK_URL"])
        XCTAssertTrue(app.staticTexts[address].exists)
        attachment(app, name: "SafariSharedItemInHost")
    }

    @MainActor private func photoCandidate(_ app: XCUIApplication) -> XCUIElement? {
        let photos = NSPredicate(format: "label CONTAINS[c] %@ OR label CONTAINS %@ OR label CONTAINS %@ OR label CONTAINS[c] %@", "photo", "写真", "画像", "screenshot")
        for surface in foregroundSurfaces(app) {
            let window = surface.windows.firstMatch
            guard window.exists else { continue }
            let viewport = window.frame
            for query in [surface.cells, surface.collectionViews.images, surface.collectionViews.buttons,
                          surface.images.matching(photos), surface.buttons.matching(photos)] {
                // Bind the actual accessibility element: picker contents can
                // change while loading, invalidating a query's numerical index.
                let images = query.allElementsBoundByAccessibilityElement.filter {
                    guard $0.exists else { return false }
                    let frame = $0.frame
                    let ratio = frame.width / max(1, frame.height)
                    return frame.width >= 60 && frame.height >= 60 && frame.width < viewport.width * 0.7
                        && ratio >= 0.6 && ratio <= 1.6 && frame.intersects(viewport)
                }
                if let fixture = images.first(where: { $0.exists && ($0.label.contains("2030") || $0.label.contains("PHOTO123")) }) { return fixture }
                if let newest = images.last { return newest }
            }
        }
        return nil
    }

    @MainActor private func shareCandidate(_ app: XCUIApplication) -> XCUIElement? {
        let predicate = NSPredicate(format: "label BEGINSWITH[c] %@ OR label BEGINSWITH %@ OR identifier CONTAINS[c] %@", "Share", "共有", "Share")
        for surface in foregroundSurfaces(app) {
            for query in [surface.buttons.matching(predicate), surface.menuItems.matching(predicate),
                          surface.staticTexts.matching(predicate), surface.cells.matching(predicate)] {
                if let element = query.allElementsBoundByAccessibilityElement.first(where: { $0.exists && $0.isHittable }) { return element }
            }
        }
        return nil
    }

    @MainActor private func activityCandidate(_ app: XCUIApplication, matching predicate: NSPredicate) -> XCUIElement? {
        // iOS can expose an activity as a cell or text inside the system sheet,
        // and the localized More label can include an ellipsis.
        for surface in foregroundSurfaces(app) {
            for query in [surface.buttons.matching(predicate), surface.cells.matching(predicate),
                          surface.staticTexts.matching(predicate)] {
                if let element = query.allElementsBoundByAccessibilityElement.first(where: { $0.exists && $0.isHittable }) { return element }
            }
        }
        return nil
    }

    @MainActor private func foregroundSurfaces(_ app: XCUIApplication) -> [XCUIApplication] {
        let system = XCUIApplication(bundleIdentifier: "com.apple.springboard")
        // Only query foreground applications. A system sheet can temporarily
        // move its host into the background, where its window no longer exists.
        return [app, system].filter { $0.state == .runningForeground }
    }

    @MainActor private func controls(_ app: XCUIApplication) -> String {
        // This class only opens synthetic CI input. Keep bounded element labels,
        // never a full view hierarchy, environment, clipboard or provider payload.
        func labels(_ query: XCUIElementQuery) -> String {
            query.allElementsBoundByAccessibilityElement.filter(\.exists).prefix(8)
                .map { "[" + ($0.isHittable ? "hit" : "nohit") + "]" + String($0.label.prefix(80)) }.joined(separator: " | ")
        }
        let system = XCUIApplication(bundleIdentifier: "com.apple.springboard")
        let systemControls = system.state == .runningForeground
            ? "; systemButtons=" + labels(system.buttons) + "; systemCells=" + labels(system.cells)
            : "; systemNotForeground=true"
        guard app.state == .runningForeground else { return "hostNotForeground=true" + systemControls }
        return "buttons=" + labels(app.buttons) + "; images=" + labels(app.images)
            + "; cells=" + labels(app.cells) + "; texts=" + labels(app.staticTexts)
            + systemControls
    }
}
