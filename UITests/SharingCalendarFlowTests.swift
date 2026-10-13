import XCTest

final class SharingCalendarFlowTests: XCTestCase {
    override func setUpWithError() throws { continueAfterFailure = false }
    @MainActor private func launch(large: Bool = false) -> XCUIApplication {
        let app = XCUIApplication()
        app.launchArguments = ["--ui-testing", large ? "--qa-dark" : "--qa-light", "-UIPreferredContentSizeCategoryName",
                               large ? "UICTContentSizeCategoryAccessibilityXXXL" : "UICTContentSizeCategoryL"]
        app.launch()
        if app.buttons["onboardingSkip"].waitForExistence(timeout: 5) { app.buttons["onboardingSkip"].tap() }
        return app
    }
    @MainActor private func reveal(_ element: XCUIElement, app: XCUIApplication) {
        // A full swipe can jump over a large control. Drag a measured short
        // distance along the list's trailing margin to keep its center visible.
        for attempt in 0..<48 {
            if fullyVisible(element, app: app) { return }
            guard element.exists else {
                if attempt < 24 { app.swipeUp() } else { app.swipeDown() }
                continue
            }
            let frame = element.frame
            let viewport = visibleArea(app)
            let upward = frame.maxY > viewport.maxY
            let gap = upward ? frame.maxY - viewport.maxY : viewport.minY - frame.minY
            let delta = min(110, max(30, gap + 16)) * (upward ? -1 : 1)
            let start = app.coordinate(withNormalizedOffset: .zero).withOffset(CGVector(dx: viewport.maxX - 8, dy: viewport.midY))
            let end = start.withOffset(CGVector(dx: 0, dy: delta))
            start.press(forDuration: 0.1, thenDragTo: end)
        }
        let picture = XCTAttachment(screenshot: app.screenshot()); picture.name = "UnreachableControl"; picture.lifetime = .keepAlways; add(picture)
        print("Reveal failed: exists=\(element.exists) frame=\(element.exists ? String(describing: element.frame) : "not present") window=\(app.windows.firstMatch.frame) navigation=\(app.navigationBars.allElementsBoundByIndex.map { $0.frame }) tabs=\(app.tabBars.allElementsBoundByIndex.map { $0.frame })")
        XCTAssertTrue(fullyVisible(element, app: app), "The control must be visible inside the navigation and tab bars")
    }
    @MainActor private func fullyVisible(_ element: XCUIElement, app: XCUIApplication) -> Bool {
        guard element.exists && element.isHittable else { return false }
        let viewport = visibleArea(app)
        let frame = element.frame
        return viewport.contains(CGPoint(x: frame.midX, y: frame.midY))
            && (frame.height > viewport.height || viewport.contains(frame))
    }
    @MainActor private func visibleArea(_ app: XCUIApplication) -> CGRect {
        let window = app.windows.firstMatch.frame
        let top = app.navigationBars.allElementsBoundByIndex.filter { $0.exists && $0.frame.intersects(window) }.map { $0.frame.maxY }.max() ?? window.minY
        let bottom = app.tabBars.allElementsBoundByIndex.filter { bar in
            bar.exists && bar.buttons.allElementsBoundByIndex.contains { $0.exists && $0.isHittable }
        }.map { $0.frame.minY }.min() ?? window.maxY
        return CGRect(x: window.minX, y: top + 4, width: window.width, height: max(0, bottom - top - 8))
    }
    @MainActor private func audit(_ app: XCUIApplication, name: String) throws {
        let picture = XCTAttachment(screenshot: app.screenshot()); picture.name = name; picture.lifetime = .keepAlways; add(picture)
        let sizing: XCUIAccessibilityAuditType = [.dynamicType, .textClipped]
        for types in [XCUIAccessibilityAuditType.all.subtracting(sizing), sizing] {
            try app.performAccessibilityAudit(for: types) { issue in
                // Returning false lets XCTest report the failure and export its
                // element image after restoring the temporary system font size.
                print("Audit [\(name)] type=\(issue.auditType.rawValue) | \(issue.detailedDescription) | identifier=\(issue.element?.identifier ?? "") label=\(issue.element?.label ?? "") frame=\(String(describing: issue.element?.frame))")
                return false
            }
        }
        var previous: [CGRect] = []; var stable = 0
        let settled = XCTNSPredicateExpectation(predicate: NSPredicate { _, _ in
            let frames = [app.navigationBars.firstMatch.frame, app.tabBars.firstMatch.frame]
            stable = frames == previous ? stable + 1 : 0; previous = frames
            return stable >= 2
        }, object: app)
        XCTAssertEqual(XCTWaiter.wait(for: [settled], timeout: 10), .completed)
    }
    @MainActor private func save(_ app: XCUIApplication, title: String, note: String = "") {
        let field = app.descendants(matching: .any).matching(identifier: "titleField").firstMatch
        XCTAssertTrue(field.waitForExistence(timeout: 5)); field.tap(); field.typeText(title)
        if !note.isEmpty {
            let memo = app.descendants(matching: .any).matching(identifier: "noteField").firstMatch
            memo.tap(); memo.typeText(note)
        }
        app.buttons["toolbarSaveButton"].tap()
    }
    @MainActor func testCalendarAddsOnSelectedDayAndCompletesWithoutLeavingCalendar() throws {
        let app = launch(); app.tabBars.buttons["今日"].tap(); app.buttons["openCalendarButton"].tap()
        XCTAssertTrue(app.navigationBars["カレンダー"].waitForExistence(timeout: 5))
        try audit(app, name: "Calendar-Light-Empty")
        reveal(app.buttons["calendarNextMonth"], app: app); app.buttons["calendarNextMonth"].tap()
        let next = app.staticTexts["calendarMonthTitle"].label
        app.buttons["calendarPreviousMonth"].tap(); XCTAssertNotEqual(next, app.staticTexts["calendarMonthTitle"].label)
        app.buttons["calendarTodayButton"].tap()
        let add = app.buttons["calendarAddButton"]; reveal(add, app: app); add.tap()
        save(app, title: "Calendar shared plan")
        XCTAssertTrue(app.staticTexts["Calendar shared plan"].waitForExistence(timeout: 5))
        reveal(app.buttons["completeButton"].firstMatch, app: app); app.buttons["completeButton"].firstMatch.tap()
        XCTAssertFalse(app.staticTexts["Calendar shared plan"].exists)
        let toggle = app.buttons["calendarCompletedToggle"]; reveal(toggle, app: app); toggle.tap()
        XCTAssertTrue(app.staticTexts["Calendar shared plan"].waitForExistence(timeout: 5))
        reveal(app.staticTexts["Calendar shared plan"], app: app)
        let image = XCTAttachment(screenshot: app.screenshot()); image.name = "Calendar-Completed"; image.lifetime = .keepAlways; self.add(image)
        let back = app.buttons["calendarCloseButton"]; reveal(back, app: app); back.tap()
        XCTAssertTrue(app.navigationBars["今日"].waitForExistence(timeout: 5))
    }
    @MainActor func testSharingPreviewRequiresOptInAndOpensNativeShareSheet() throws {
        let app = launch(); app.buttons["addButton"].tap(); save(app, title: "Share copy", note: "Synthetic private note")
        app.buttons["detailButton"].firstMatch.tap(); app.buttons["shareItemButton"].tap()
        let preview = app.staticTexts["sharePreview"]; XCTAssertTrue(preview.waitForExistence(timeout: 5))
        XCTAssertFalse(preview.label.contains("Synthetic private note"))
        app.buttons["shareNoteToggle"].tap()
        let noteVisible = XCTNSPredicateExpectation(predicate: NSPredicate(format: "label CONTAINS %@", "Synthetic private note"), object: preview)
        XCTAssertEqual(XCTWaiter.wait(for: [noteVisible], timeout: 5), .completed)
        try audit(app, name: "Share-Light-Preview")
        let share = app.buttons["shareTextButton"]; reveal(share, app: app); share.tap()
        let ready = XCTNSPredicateExpectation(predicate: NSPredicate { _, _ in self.copyAction(app) != nil }, object: app)
        let result = XCTWaiter.wait(for: [ready], timeout: 10)
        let picture = XCTAttachment(screenshot: app.screenshot()); picture.name = "NativeTextShareSheet"; picture.lifetime = .keepAlways; add(picture)
        XCTAssertEqual(result, .completed, "Native sharing must offer copy without sending to anyone")
        let copy = try XCTUnwrap(copyAction(app))
        copy.tap()
        XCTAssertTrue(app.navigationBars["項目を共有"].waitForExistence(timeout: 5))
    }
    @MainActor private func copyAction(_ app: XCUIApplication) -> XCUIElement? {
        let system = XCUIApplication(bundleIdentifier: "com.apple.springboard")
        let predicate = NSPredicate(format: "label IN %@", ["Copy", "コピー"])
        for surface in [app, system].filter({ $0.state == .runningForeground }) {
            for query in [surface.buttons.matching(predicate), surface.cells.matching(predicate), surface.staticTexts.matching(predicate)] {
                if let value = query.allElementsBoundByIndex.first(where: { $0.exists && $0.isHittable }) { return value }
            }
        }
        return nil
    }
    @MainActor func testDarkLargestTextCalendarAndSharingRemainUsable() throws {
        let app = launch(large: true)
        app.tabBars.buttons["今日"].tap(); reveal(app.buttons["openCalendarButton"], app: app); app.buttons["openCalendarButton"].tap()
        reveal(app.buttons["calendarChooseDayButton"], app: app)
        XCTAssertTrue(app.buttons["calendarChooseDayButton"].waitForExistence(timeout: 5))
        try audit(app, name: "Calendar-Dark-LargestText")
        reveal(app.buttons["calendarChooseDayButton"], app: app)
        app.buttons["calendarChooseDayButton"].tap()
        XCTAssertTrue(app.navigationBars["日付を選ぶ"].waitForExistence(timeout: 5))
        try audit(app, name: "Calendar-DateList-Dark-LargestText")
        let close = app.buttons["calendarChooseCloseButton"]; reveal(close, app: app); close.tap()
        let choose = app.buttons["calendarChooseDayButton"]; reveal(choose, app: app); choose.tap()
        XCTAssertTrue(app.navigationBars["日付を選ぶ"].waitForExistence(timeout: 5))
        let first = app.buttons["calendarChooseDay_1"]; reveal(first, app: app); first.tap()
        let add = app.buttons["calendarAddButton"]; reveal(add, app: app); add.tap()
        save(app, title: "Large calendar note")
        let detail = app.buttons["detailButton"].firstMatch; reveal(detail, app: app); detail.tap()
        let share = app.buttons["shareItemButton"]; reveal(share, app: app); share.tap()
        reveal(app.staticTexts["sharePreview"], app: app)
        XCTAssertTrue(app.staticTexts["sharePreview"].waitForExistence(timeout: 5))
        try audit(app, name: "Share-Dark-LargestText")
        reveal(app.buttons["shareFileButton"], app: app)
        try audit(app, name: "Share-FileAction-Dark-LargestText")
        reveal(app.buttons["shareFileButton"], app: app)
        XCTAssertGreaterThanOrEqual(app.buttons["shareFileButton"].frame.height, 44)
        XCTAssertTrue(app.buttons["shareFileButton"].isEnabled)
    }
}
