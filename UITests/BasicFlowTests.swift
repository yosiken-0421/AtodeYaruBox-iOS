import XCTest

final class BasicFlowTests: XCTestCase {
    override func setUpWithError() throws { continueAfterFailure = false }
    private func launch() -> XCUIApplication {
        let app = XCUIApplication()
        app.launchArguments = ["--ui-testing", "--qa-light", "-UIPreferredContentSizeCategoryName", "UICTContentSizeCategoryL"]
        app.launch()
        if app.buttons["onboardingSkip"].waitForExistence(timeout: 5) { app.buttons["onboardingSkip"].tap() }
        return app
    }
    private func create(_ app: XCUIApplication, title: String) {
        let add = app.buttons["addButton"]
        XCTAssertTrue(add.waitForExistence(timeout: 5)); add.tap()
        let field = app.descendants(matching: .any).matching(identifier: "titleField").firstMatch
        XCTAssertTrue(field.waitForExistence(timeout: 5)); field.tap(); field.typeText(title)
        app.buttons["toolbarSaveButton"].tap()
        XCTAssertTrue(app.staticTexts[title].waitForExistence(timeout: 5))
    }
    func testLaunchAndTabs() {
        let app = launch()
        for tab in ["箱", "今日", "探す", "設定"] { XCTAssertTrue(app.tabBars.buttons[tab].exists) }
    }
    func testCreateSaveSnoozeCompleteAndSearchHistory() {
        let app = launch()
        let title = "QA-" + UUID().uuidString.prefix(8)
        create(app, title: title)
        app.buttons["snoozeButton"].firstMatch.tap()
        XCTAssertTrue(app.buttons["snooze_hour"].waitForExistence(timeout: 5))
        app.buttons["snooze_hour"].tap()
        XCTAssertTrue(app.buttons["completeButton"].firstMatch.waitForExistence(timeout: 5))
        app.buttons["completeButton"].firstMatch.tap()
        XCTAssertFalse(app.staticTexts[title].exists)
        app.tabBars.buttons["探す"].tap()
        let search = app.textFields["searchField"]
        XCTAssertTrue(search.waitForExistence(timeout: 5)); search.tap(); search.typeText(title)
        XCTAssertTrue(app.staticTexts[title].waitForExistence(timeout: 5))
        let submit = app.buttons["searchSubmitButton"]
        XCTAssertTrue(submit.waitForExistence(timeout: 5)); submit.tap()
        let searchSubmitted = XCTNSPredicateExpectation(predicate: NSPredicate { _, _ in app.keyboards.count == 0 }, object: app)
        XCTAssertEqual(XCTWaiter.wait(for: [searchSubmitted], timeout: 5), .completed,
            "The visible search button must finish text entry")
        let settingsTab = app.tabBars.buttons["設定"]
        settingsTab.tap()
        let keyboardDismissed = XCTNSPredicateExpectation(predicate: NSPredicate { _, _ in app.keyboards.count == 0 }, object: app)
        XCTAssertEqual(XCTWaiter.wait(for: [keyboardDismissed], timeout: 5), .completed, "Leaving search must dismiss its keyboard")
        let settingsSelected = XCTNSPredicateExpectation(predicate: NSPredicate { _, _ in settingsTab.isSelected }, object: settingsTab)
        XCTAssertEqual(XCTWaiter.wait(for: [settingsSelected], timeout: 5), .completed,
            "Settings tab must become selected after one tap; searchSelected=\(app.tabBars.buttons["探す"].isSelected)")
        XCTAssertTrue(app.buttons["defaultReminderModePicker"].waitForExistence(timeout: 5),
            "Settings content must appear after leaving search")
        let history = app.descendants(matching: .any).matching(identifier: "completedHistoryButton").firstMatch
        XCTAssertTrue(history.waitForExistence(timeout: 5), "History navigation must be exposed to accessibility")
        XCTAssertTrue(history.isEnabled)
        for _ in 0..<8 {
            if history.exists && history.isHittable { break }
            app.swipeDown()
        }
        for _ in 0..<16 {
            if history.exists && history.isHittable { break }
            app.swipeUp()
        }
        XCTAssertGreaterThanOrEqual(history.frame.width, 44)
        XCTAssertGreaterThanOrEqual(history.frame.height, 44)
        XCTAssertTrue(history.isHittable); history.tap()
        XCTAssertTrue(app.navigationBars["完了履歴"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.staticTexts[title].waitForExistence(timeout: 5))
    }
    func testInvalidURLDoesNotDismissComposer() {
        let app = launch()
        app.buttons["addButton"].tap()
        let title = app.descendants(matching: .any).matching(identifier: "titleField").firstMatch
        title.tap(); title.typeText("Invalid URL")
        let url = app.textFields["urlField"]; url.tap(); url.typeText("javascript:alert(1)")
        app.buttons["toolbarSaveButton"].tap()
        XCTAssertTrue(app.alerts["入力を確認してください"].waitForExistence(timeout: 5))
    }
    func testDarkModeAndLargeTextSmoke() {
        let app = XCUIApplication()
        app.launchArguments = ["--ui-testing", "--qa-dark", "-UIPreferredContentSizeCategoryName", "UICTContentSizeCategoryAccessibilityXXXL"]
        app.launch()
        if app.buttons["onboardingSkip"].waitForExistence(timeout: 5) { app.buttons["onboardingSkip"].tap() }
        XCTAssertTrue(app.buttons["addButton"].waitForExistence(timeout: 5))
        let attachment = XCTAttachment(screenshot: app.screenshot())
        attachment.name = "Dark-AccessibilityXXXL"; attachment.lifetime = .keepAlways
        add(attachment)
    }
}
