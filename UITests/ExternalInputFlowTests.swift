import XCTest
import Vision

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
        // The selected CI guest contains stock samples and a generated image. Finish the
        // stock library's first-run UI before asking its remote picker to load.
        if ProcessInfo.processInfo.operatingSystemVersion.majorVersion == 18 {
        let library = XCUIApplication(bundleIdentifier: "com.apple.mobileslideshow")
        library.launch()
        let continueButton = library.buttons.matching(NSPredicate(format: "label IN %@", ["Continue", "続ける", "Get Started", "使い始める"])).firstMatch
        if continueButton.waitForExistence(timeout: 3), continueButton.isHittable { continueButton.tap() }
        _ = library.collectionViews.cells.firstMatch.waitForExistence(timeout: 10)
        // On a cold iOS 18 guest, Photos' welcome sheet is drawn but omitted
        // from its AX button query. Read only this synthetic guest's screen and
        // tap the observed Continue label; no account or permission is accepted.
        try finishSyntheticPhotosWelcome(library)
        let system = XCUIApplication(bundleIdentifier: "com.apple.springboard")
        let photosAlert = system.alerts.matching(NSPredicate(format: "label CONTAINS %@", "Photos")).firstMatch
        if photosAlert.waitForExistence(timeout: 3) {
            let deny = photosAlert.buttons.matching(NSPredicate(format: "label IN %@", ["Don’t Allow", "Don't Allow", "許可しない"])).firstMatch
            XCTAssertTrue(deny.exists, "Only the stock Photos notification prompt may be dismissed here")
            deny.tap()
        }
        // iOS 18's main Photos mosaic does not expose collection-view cells.
        // Confirm the observed library screen instead, keeping the real picker
        // selection and subsequent OCR assertions unchanged.
        let loaded = XCTNSPredicateExpectation(predicate: NSPredicate { _, _ in
            let text = (try? self.screenText(library)) ?? ""
            return text.contains("photos") && text.contains("recent days")
                && !text.contains("would like to send") && !text.contains("what's new")
        }, object: library)
        let libraryResult = XCTWaiter.wait(for: [loaded], timeout: 10)
        attachment(library, name: "SyntheticPhotosLibraryBeforePicker")
        XCTAssertEqual(libraryResult, .completed, "The synthetic library must finish onboarding before its remote picker opens")
        }
        let app = host()
        app.buttons["addButton"].tap()
        let choose = app.buttons["写真を選ぶ"]
        XCTAssertTrue(choose.waitForExistence(timeout: 5))
        choose.tap()
        attachment(app, name: "ActualPhotosPickerBeforeSelection")
        // Let the system library finish its initial load before querying thumbnails.
        // The remote system picker can omit its thumbnails from the host AX
        // tree. Locate the unique marker visibly rendered in this CI-only image.
        let photoReady = NSPredicate { _, _ in (try? self.fixturePhotoPoint(app)) != nil }
        let ready = XCTNSPredicateExpectation(predicate: photoReady, object: app)
        let readyResult = XCTWaiter.wait(for: [ready], timeout: 45)
        attachment(app, name: "ActualPhotosPickerAfterLoadingWait")
        XCTAssertEqual(readyResult, .completed, "PHOTO_PICKER_NO_VISIBLE_CELL; " + controls(app))
        let point = try XCTUnwrap(fixturePhotoPoint(app))
        let selectedLabel = "Observed synthetic PHOTO123 thumbnail"
        attachment(app, name: "ActualPhotosPicker")
        app.coordinate(withNormalizedOffset: point).tap()
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
        app.buttons["detailButton"].firstMatch.tap()
        XCTAssertTrue(app.staticTexts["返品"].waitForExistence(timeout: 5), "The selected screenshot must retain its detected action after saving")
        let edit = app.buttons["editItemButton"]
        XCTAssertTrue(edit.waitForExistence(timeout: 5))
        XCTAssertEqual(edit.label, "編集")
        XCTAssertGreaterThanOrEqual(edit.frame.height, 44)
        attachment(app, name: "PhotoOCRSavedAndSearchable")
    }

    @MainActor private func finishSyntheticPhotosWelcome(_ library: XCUIApplication) throws {
        for _ in 0..<2 {
            guard let image = library.screenshot().image.cgImage else { return }
            let request = VNRecognizeTextRequest()
            request.recognitionLanguages = ["en-US"]
            request.recognitionLevel = .accurate
            request.usesLanguageCorrection = false
            try VNImageRequestHandler(cgImage: image).perform([request])
            let observations = request.results ?? []
            let text = observations.compactMap { $0.topCandidates(1).first?.string }.joined(separator: " ")
                .lowercased().replacingOccurrences(of: "’", with: "'")
            guard text.contains("photos"), text.contains("what's new") || text.contains("welcome"),
                  let button = observations.first(where: { $0.topCandidates(1).first?.string.lowercased() == "continue" }) else { return }
            let box = button.boundingBox
            library.coordinate(withNormalizedOffset: CGVector(dx: box.midX, dy: 1 - box.midY)).tap()
            _ = library.collectionViews.cells.firstMatch.waitForExistence(timeout: 5)
        }
    }

    @MainActor private func screenText(_ app: XCUIApplication) throws -> String {
        guard let image = app.screenshot().image.cgImage else { return "" }
        let request = VNRecognizeTextRequest()
        request.recognitionLanguages = ["en-US"]
        request.recognitionLevel = .accurate
        request.usesLanguageCorrection = false
        try VNImageRequestHandler(cgImage: image).perform([request])
        return (request.results ?? []).compactMap { $0.topCandidates(1).first?.string }.joined(separator: " ").lowercased()
    }

    @MainActor private func fixturePhotoPoint(_ app: XCUIApplication) throws -> CGVector? {
        guard let image = app.screenshot().image.cgImage else { return nil }
        let request = VNRecognizeTextRequest()
        request.recognitionLanguages = ["en-US"]
        request.recognitionLevel = .accurate
        request.usesLanguageCorrection = false
        try VNImageRequestHandler(cgImage: image).perform([request])
        guard let marker = (request.results ?? []).first(where: {
            let value = ($0.topCandidates(1).first?.string ?? "").uppercased()
                .filter { $0.isLetter || $0.isNumber }
            // The gallery crops the image's left edge. Match either its unique
            // printed date or marker, tolerating only the I/1 glyph ambiguity.
            return value.contains("20301008") || value.replacingOccurrences(of: "I", with: "1").contains("PHOTO123")
        }) else { return nil }
        let box = marker.boundingBox
        return CGVector(dx: box.midX, dy: 1 - box.midY)
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
        field.coordinate(withNormalizedOffset: CGVector(dx: 0.95, dy: 0.5)).tap()
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
        app.buttons["detailButton"].firstMatch.tap()
        XCTAssertTrue(app.buttons["確認しました"].waitForExistence(timeout: 5))
        let address = try XCTUnwrap(ProcessInfo.processInfo.environment["ATODE_QA_LOOPBACK_URL"])
        reveal(app.staticTexts[address], in: app)
        XCTAssertTrue(app.staticTexts[address].exists)
        attachment(app, name: "SafariSharedItemInHost")
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
