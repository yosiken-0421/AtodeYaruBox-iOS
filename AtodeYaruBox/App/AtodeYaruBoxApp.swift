import SwiftUI
import SwiftData

@main
@MainActor
struct AtodeYaruBoxApp: App {
    @UIApplicationDelegateAdaptor(NotificationDelegate.self) private var delegate
    @State private var session: AppSession?
    @State private var startupError: String?

    init() {
        do {
            let newSession = AppSession(container: try SharedStore.container(inMemory: ProcessInfo.processInfo.arguments.contains("--ui-testing")))
            _session = State(initialValue: newSession)
            NotificationDelegate.session = newSession
        } catch { _startupError = State(initialValue: error.localizedDescription) }
    }

    var body: some Scene {
        WindowGroup {
            if let session {
                RootView().environment(session).modelContainer(session.container)
                    .preferredColorScheme(qaColorScheme)
            } else {
                ContentUnavailableView {
                    Label("保存場所を開けません", systemImage: "externaldrive.badge.exclamationmark")
                } description: {
                    Text("保存データは削除していません。空き容量を確認して、もう一度お試しください。")
                } actions: {
                    Button("もう一度開く") {
                        do {
                            let newSession = AppSession(container: try SharedStore.container(inMemory: ProcessInfo.processInfo.arguments.contains("--ui-testing")))
                            session = newSession; NotificationDelegate.session = newSession; startupError = nil
                        } catch { startupError = error.localizedDescription }
                    }
                    if let startupError { Text(startupError).font(.footnote).foregroundStyle(.secondary) }
                }
            }
        }
    }

    private var qaColorScheme: ColorScheme? {
        let arguments = ProcessInfo.processInfo.arguments
        if arguments.contains("--qa-dark") { return .dark }
        if arguments.contains("--qa-light") { return .light }
        return nil
    }
}
