import XCTest

final class AccessibilityFlowTests: XCTestCase {
    // Collect findings across the screens in one run. Every finding still fails
    // its XCTest case and the strict CI gate; no audit issue is excluded.
    override func setUpWithError() throws { continueAfterFailure = true }

    @MainActor private func launch(dark: Bool = false, largeText: Bool = false) -> XCUIApplication {
        let app = XCUIApplication()
        app.launchArguments = ["--ui-testing"]
        app.launchArguments.append(dark ? "--qa-dark" : "--qa-light")
        if largeText {
            app.launchArguments += ["-UIPreferredContentSizeCategoryName", "UICTContentSizeCategoryAccessibilityXXXL"]
        }
        app.launch()
        if app.buttons["onboardingSkip"].waitForExistence(timeout: 5) {
            app.buttons["onboardingSkip"].tap()
        }
        XCTAssertTrue(app.tabBars.buttons["箱"].waitForExistence(timeout: 5))
        return app
    }

    @MainActor private func audit(_ app: XCUIApplication, name: String) {
        let image = XCTAttachment(screenshot: app.screenshot())
        image.name = name
        image.lifetime = .keepAlways
        add(image)
        // Every issue fails the test. No label, contrast, clipping or target-size exclusions.
        do {
            try app.performAccessibilityAudit { issue in
                let element = issue.element
                let type = issue.auditType
                let kinds = [(XCUIAccessibilityAuditType.contrast, "CONTRAST"), (.dynamicType, "DYNAMIC_TYPE"),
                             (.textClipped, "TEXT_CLIPPED"), (.hitRegion, "HIT_REGION"),
                             (.elementDetection, "ELEMENT_DETECTION"), (.sufficientElementDescription, "ELEMENT_DESCRIPTION"),
                             (.trait, "TRAIT")]
                    .filter { type.contains($0.0) }.map { $0.1 }.joined(separator: ",")
                XCTFail("Accessibility audit [\(name)]: kind=\(kinds) rawType=\(type.rawValue) | \(issue.compactDescription) | \(issue.detailedDescription) | element=\(element?.identifier ?? "") label=\(element?.label ?? "") frame=\(String(describing: element?.frame))")
                return false
            }
        } catch {
            // Preserve the audit failure, while inspecting subsequent tabs too.
            XCTFail("Accessibility audit [\(name)] did not complete cleanly: \(error)")
        }
    }

    @MainActor private func selectTab(_ app: XCUIApplication, label: String) {
        let tab = app.tabBars.buttons[label]
        tab.tap()
        let ready = XCTNSPredicateExpectation(predicate: NSPredicate { _, _ in
            tab.isSelected && app.navigationBars[label].exists
        }, object: app)
        XCTAssertEqual(XCTWaiter.wait(for: [ready], timeout: 5), .completed,
            "The selected screen must be visible before its accessibility audit")
    }

    @MainActor private func reveal(_ element: XCUIElement, in app: XCUIApplication) {
        // A system audit can leave a scrolling form at a different position.
        // Look in both directions, rather than assuming every control is below.
        for _ in 0..<8 {
            if element.exists && element.isHittable { return }
            app.swipeDown()
        }
        for _ in 0..<16 {
            if element.exists && element.isHittable { return }
            app.swipeUp()
        }
        XCTAssertTrue(element.isHittable, "The control must be reachable by ordinary scrolling")
    }

    @MainActor private func verifyNotificationSettings(_ app: XCUIApplication, name: String) {
        let selector = app.buttons["defaultReminderModePicker"]
        reveal(selector, in: app)
        selector.tap()
        let normal = app.buttons["reminderModeChoice_normal"]
        XCTAssertTrue(normal.waitForExistence(timeout: 5))
        audit(app, name: name + "-NotificationModes")
        reveal(normal, in: app)
        normal.tap()
        let normalSelected = NSPredicate(format: "label == %@", "新しい項目の通知：普通")
        let selectionUpdated = XCTNSPredicateExpectation(predicate: normalSelected, object: selector)
        XCTAssertEqual(XCTWaiter.wait(for: [selectionUpdated], timeout: 5), .completed)

        let privacy = app.buttons["notificationTitlesToggle"]
        reveal(privacy, in: app)
        let original = privacy.label
        privacy.tap()
        XCTAssertNotEqual(privacy.label, original)
        privacy.tap()
        XCTAssertEqual(privacy.label, original)
    }

    @MainActor func testAllTabsAccessibilityInLightMode() throws {
        let app = launch()
        for tab in ["箱", "今日", "探す", "設定"] {
            selectTab(app, label: tab)
            audit(app, name: "Light-" + tab)
        }
        verifyNotificationSettings(app, name: "Light")
    }

    @MainActor func testAllTabsAccessibilityInDarkMode() throws {
        let app = launch(dark: true)
        for tab in ["箱", "今日", "探す", "設定"] {
            selectTab(app, label: tab)
            audit(app, name: "Dark-" + tab)
        }
        verifyNotificationSettings(app, name: "Dark")
    }

    @MainActor func testLargestTextKeepsSaveSnoozeAndCompleteUsable() throws {
        let app = launch(largeText: true)
        app.buttons["addButton"].tap()
        let field = app.descendants(matching: .any).matching(identifier: "titleField").firstMatch
        XCTAssertTrue(field.waitForExistence(timeout: 5))
        field.tap()
        let title = "あとで確認する大切なメモ"
        field.typeText(title)
        app.buttons["toolbarSaveButton"].tap()
        XCTAssertTrue(app.staticTexts[title].waitForExistence(timeout: 5))
        audit(app, name: "LargestText-Item")

        app.buttons["snoozeButton"].firstMatch.tap()
        XCTAssertTrue(app.buttons["snooze_hour"].waitForExistence(timeout: 5))
        audit(app, name: "LargestText-Snooze")
        app.buttons["snooze_hour"].tap()
        let complete = app.buttons["completeButton"].firstMatch
        XCTAssertTrue(complete.waitForExistence(timeout: 5))
        complete.tap()
        XCTAssertFalse(app.staticTexts[title].exists)
        audit(app, name: "LargestText-Completed")
        app.tabBars.buttons["設定"].tap()
        audit(app, name: "LargestText-Settings")
        verifyNotificationSettings(app, name: "LargestText")
    }
}
