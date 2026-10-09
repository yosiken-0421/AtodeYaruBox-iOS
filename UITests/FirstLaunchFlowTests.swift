import XCTest

final class FirstLaunchFlowTests: XCTestCase {
    override func setUpWithError() throws { continueAfterFailure = false }

    @MainActor func testThreeIntroductionPagesLeadToAnEmptyBoxWithoutPermissionPrompts() throws {
        let app = XCUIApplication()
        app.launchArguments = ["--ui-testing", "--qa-onboarding", "--qa-light",
            "-UIPreferredContentSizeCategoryName", "UICTContentSizeCategoryAccessibilityXXXL"]
        app.launch()
        let next = app.buttons["onboardingNext"]
        for (index,title) in ["あとでやる箱", "何でも保存できます", "必要な時に知らせます"].enumerated() {
            XCTAssertTrue(app.staticTexts[title].waitForExistence(timeout: 5))
            XCTAssertTrue(app.staticTexts["\(index + 1) / 3"].exists)
            XCTAssertEqual(app.alerts.count, 0, "First launch must not request unrelated permissions")
            let pageImage = XCTAttachment(screenshot: app.screenshot())
            pageImage.name = "LargestText-Introduction-\(index + 1)-Heading"
            pageImage.lifetime = .keepAlways
            add(pageImage)
            try app.performAccessibilityAudit()
            for _ in 0..<8 {
                if next.isHittable { break }
                app.swipeUp()
            }
            XCTAssertTrue(next.isHittable, "The normal next button must remain reachable at the largest text size")
            XCTAssertGreaterThanOrEqual(next.frame.height, 44)
            XCTAssertEqual(next.label, index < 2 ? "次へ" : "はじめる")
            let buttonImage = XCTAttachment(screenshot: app.screenshot())
            buttonImage.name = "LargestText-Introduction-\(index + 1)-Next"
            buttonImage.lifetime = .keepAlways
            add(buttonImage)
            next.tap()
        }
        XCTAssertTrue(app.tabBars.buttons["箱"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.staticTexts["箱はすっきり"].exists)
        XCTAssertEqual(app.alerts.count, 0)
        app.terminate()
        app.launchArguments = ["--ui-testing", "--qa-light"]
        app.launch()
        XCTAssertTrue(app.tabBars.buttons["箱"].waitForExistence(timeout: 5))
        XCTAssertFalse(app.buttons["onboardingNext"].exists, "Finished introduction must not repeat on relaunch")
    }
}
