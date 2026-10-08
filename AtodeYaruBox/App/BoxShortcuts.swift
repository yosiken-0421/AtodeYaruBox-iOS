import AppIntents

struct BoxShortcuts: AppShortcutsProvider {
    static var appShortcuts: [AppShortcut] {
        AppShortcut(intent: SaveToBoxIntent(), phrases: ["\(.applicationName)に保存"], shortTitle: "箱に保存", systemImageName: "tray.and.arrow.down")
        AppShortcut(intent: OpenTodayIntent(), phrases: ["\(.applicationName)の今日を開く"], shortTitle: "今日を開く", systemImageName: "sun.max")
        AppShortcut(intent: NewMemoIntent(), phrases: ["\(.applicationName)で新しいメモ"], shortTitle: "新規メモ", systemImageName: "square.and.pencil")
        AppShortcut(intent: NextItemIntent(), phrases: ["\(.applicationName)の次の項目"], shortTitle: "次の項目", systemImageName: "arrow.right.circle")
    }
}
