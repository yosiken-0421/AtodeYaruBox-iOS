import SwiftUI

struct SettingsView: View {
    @Environment(AppSession.self) private var session
    @AppStorage("defaultReminderMode") private var reminderMode = ReminderMode.normal.rawValue
    @AppStorage("showNotificationTitles", store: UserDefaults(suiteName: SharedStore.groupID) ?? .standard) private var showTitles = false
    @Environment(\.openURL) private var openURL
    @State private var showingReminderModes = false
    var body: some View {
        Form {
            Section {
                NavigationLink { CompletedHistoryView() } label: {
                    BoxStatusText(text: "完了履歴", headline: true, identifier: "completedHistoryTitle")
                        .frame(minHeight: 44)
                }.accessibilityIdentifier("completedHistoryButton")
            } header: {
                BoxStatusText(text: "完了した項目", headline: true, identifier: "settingsHistoryHeading")
            }
            Section {
                BoxActionButton(title: "新しい項目の通知：" + (ReminderMode(rawValue: reminderMode) ?? .normal).label,
                    symbol: "bell", identifier: "defaultReminderModePicker", hint: "知らせ方を選びます") {
                        showingReminderModes = true
                    }
                BoxActionButton(title: "通知にタイトルを表示：" + (showTitles ? "ON" : "OFF"),
                    symbol: showTitles ? "checkmark.square" : "square", identifier: "notificationTitlesToggle",
                    hint: showTitles ? "タップするとタイトルを隠します" : "タップするとタイトルを表示します") {
                        showTitles.toggle()
                    }
                BoxStatusText(text: "静か：音なし。普通：1回。強め：1時間おきに最大2回。絶対忘れない：1時間おきに最大3回。集中モードなどにより通知が遅れることがあります。",
                    identifier: "notificationStrengthExplanation")
                BoxStatusText(text: "日時は最大48件、場所は最大16件を登録します。次回アプリを開くと通知を更新します。",
                    identifier: "notificationBudgetExplanation")
                BoxActionButton(title: "iPhoneの設定を開く", symbol: "gearshape", identifier: "openSystemSettingsButton") {
                    if let url = URL(string: UIApplication.openSettingsURLString) { openURL(url) }
                }
            } header: {
                BoxStatusText(text: "通知", headline: true, identifier: "settingsNotificationHeading")
            }
            Section {
                BoxStatusText(text: "文字の読み取りは端末内", identifier: "localOCRExplanation")
                BoxStatusText(text: "アカウント登録は不要", identifier: "noAccountExplanation")
                BoxStatusText(text: "写真は選んだものだけ", identifier: "selectedPhotosExplanation")
                privacyStatus("クラウドAI", value: "OFF・未接続")
                privacyStatus("画像のクラウド送信", value: "OFF")
                privacyStatus("iCloud同期", value: "OFF・未構成")
                BoxStatusText(text: "広告・アクセス解析・自動アップロードはありません。クラウドAIとiCloud同期は、接続設定と安全性の確認後に提供する予定です。",
                    identifier: "externalDataExplanation")
            } header: {
                BoxStatusText(text: "プライバシー", headline: true, identifier: "settingsPrivacyHeading")
            }
            Section {
                BoxStatusText(text: "保存したものを、実際に終わらせるための箱。", identifier: "boxPurposeExplanation")
                privacyStatus("バージョン", value: Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "0.1.0")
            } header: {
                BoxStatusText(text: "あとでやる箱", headline: true, identifier: "settingsAboutHeading")
            }
        }.font(.body).foregroundStyle(Color.primary).navigationTitle("設定")
            .onChange(of: showTitles) { _, _ in session.refreshSideEffects() }
            .fullScreenCover(isPresented: $showingReminderModes) { NotificationModeSheet(selectedRawValue: $reminderMode) }
    }

    private func privacyStatus(_ title: String, value: String) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            BoxStatusText(text: title, headline: true, identifier: "privacyTitle_" + title)
            BoxStatusText(text: value, identifier: "privacyValue_" + title)
        }
    }
}
