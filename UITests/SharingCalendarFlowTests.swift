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
        for _ in 0..<12 { if element.exists && element.isHittable { return }; app.swipeUp() }
        for _ in 0..<12 { if element.exists && element.isHittable { return }; app.swipeDown() }
        XCTAssertTrue(element.isHittable)
    }
    @MainActor private func audit(_ app: XCUIApplication, name: String) throws {
        let picture = XCTAttachment(screenshot: app.screenshot()); picture.name = name; picture.lifetime = .keepAlways; add(picture)
        let sizing: XCUIAccessibilityAuditType = [.dynamicType, .textClipped]
        for types in [XCUIAccessibilityAuditType.all.subtracting(sizing), sizing] { try app.performAccessibilityAudit(for: types) }
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
        let toggle = app.switches["calendarCompletedToggle"]; reveal(toggle, app: app); toggle.tap()
        XCTAssertTrue(app.staticTexts["Calendar shared plan"].waitForExistence(timeout: 5))
        reveal(app.staticTexts["Calendar shared plan"], app: app)
        let image = XCTAttachment(screenshot: app.screenshot()); image.name = "Calendar-Completed"; image.lifetime = .keepAlways; self.add(image)
    }
    @MainActor func testSharingPreviewRequiresOptInAndOpensNativeShareSheet() throws {
        let app = launch(); app.buttons["addButton"].tap(); save(app, title: "Share copy", note: "Synthetic private note")
        app.buttons["detailButton"].firstMatch.tap(); app.buttons["shareItemButton"].tap()
        let preview = app.staticTexts["sharePreview"]; XCTAssertTrue(preview.waitForExistence(timeout: 5))
        XCTAssertFalse(preview.label.contains("Synthetic private note"))
        app.switches["shareNoteToggle"].tap(); XCTAssertTrue(preview.label.contains("Synthetic private note"))
        try audit(app, name: "Share-Light-Preview")
        let share = app.buttons["shareTextButton"]; reveal(share, app: app); share.tap()
        let copy = app.buttons.matching(NSPredicate(format: "label IN %@", ["Copy", "コピー"])).firstMatch
        XCTAssertTrue(copy.waitForExistence(timeout: 10), "Native sharing must offer copy without sending to anyone")
        copy.tap()
        XCTAssertTrue(app.navigationBars["項目を共有"].waitForExistence(timeout: 5))
    }
    @MainActor func testDarkLargestTextCalendarAndSharingRemainUsable() throws {
        let app = launch(large: true)
        app.tabBars.buttons["今日"].tap(); reveal(app.buttons["openCalendarButton"], app: app); app.buttons["openCalendarButton"].tap()
        XCTAssertTrue(app.buttons["calendarChooseDayButton"].waitForExistence(timeout: 5))
        try audit(app, name: "Calendar-Dark-LargestText")
        app.buttons["calendarChooseDayButton"].tap()
        XCTAssertTrue(app.navigationBars["日付を選ぶ"].waitForExistence(timeout: 5))
        let first = app.buttons["calendarDay_1"]; reveal(first, app: app); first.tap()
        let add = app.buttons["calendarAddButton"]; reveal(add, app: app); add.tap()
        save(app, title: "Large calendar note")
        let detail = app.buttons["detailButton"].firstMatch; reveal(detail, app: app); detail.tap()
        let share = app.buttons["shareItemButton"]; reveal(share, app: app); share.tap()
        XCTAssertTrue(app.staticTexts["sharePreview"].waitForExistence(timeout: 5))
        try audit(app, name: "Share-Dark-LargestText")
        reveal(app.buttons["shareFileButton"], app: app)
        XCTAssertGreaterThanOrEqual(app.buttons["shareFileButton"].frame.height, 44)
        XCTAssertTrue(app.buttons["shareFileButton"].isEnabled)
    }
}
