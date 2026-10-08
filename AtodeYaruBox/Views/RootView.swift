import SwiftUI

struct RootView: View {
    @Environment(AppSession.self) private var session
    @Environment(\.scenePhase) private var scenePhase
    @AppStorage("hasFinishedOnboarding") private var hasFinishedOnboarding = false
    @State private var notificationItem: InboxItem?
    @FocusState private var searchIsFocused: Bool

    var body: some View {
        @Bindable var session = session
        TabView(selection: Binding(get: { session.selectedTab }, set: { tab in
            // End text entry before the native tab changes its navigation stack.
            searchIsFocused = false
            session.selectedTab = tab
        })) {
            NavigationStack { BoxView() }.tabItem { Label("箱", systemImage: "tray") }.tag(0)
            NavigationStack { TodayView() }.tabItem { Label("今日", systemImage: "sun.max") }.tag(1)
            NavigationStack { SearchView(searchFocus: $searchIsFocused) }.tabItem { Label("探す", systemImage: "magnifyingglass") }.tag(2)
            NavigationStack { SettingsView() }.tabItem { Label("設定", systemImage: "gearshape") }.tag(3)
        }
        .tint(.boxAccent)
        .sheet(isPresented: $session.showingComposer) { NavigationStack { ComposeView() } }
        .sheet(item: $notificationItem) { item in NavigationStack { ItemDetailView(item: item) } }
        .fullScreenCover(isPresented: Binding(get: { !hasFinishedOnboarding }, set: { hasFinishedOnboarding = !$0 })) {
            OnboardingView { hasFinishedOnboarding = true }
        }
        .alert("操作を完了できませんでした", isPresented: Binding(
            get: { session.errorMessage != nil }, set: { if !$0 { session.errorMessage = nil } })) {
            Button("閉じる", role: .cancel) { session.errorMessage = nil }
        } message: { Text(session.errorMessage ?? "") }
        .alert("お知らせ", isPresented: Binding(
            get: { session.noticeMessage != nil }, set: { if !$0 { session.noticeMessage = nil } })) {
            Button("わかりました", role: .cancel) { session.noticeMessage = nil }
        } message: { Text(session.noticeMessage ?? "") }
        .task {
            session.openPendingRoute(); session.refreshSideEffects()
            if let id = session.requestedItemID {
                notificationItem = try? session.repository.find(id)
                session.requestedItemID = nil
            }
        }
        .onReceive(NotificationCenter.default.publisher(for: RouteStore.changed)) { _ in session.openPendingRoute() }
        .onChange(of: scenePhase) { _, phase in if phase == .active { session.openPendingRoute(); session.refreshSideEffects() } }
        .onChange(of: session.selectedTab) { _, tab in if tab != 2 { searchIsFocused = false } }
        .onChange(of: session.requestedItemID) { _, id in
            guard let id else { return }
            notificationItem = try? session.repository.find(id)
            session.requestedItemID = nil
        }
        .onOpenURL { url in
            guard url.scheme == "atodeyarubox" else { return }
            switch url.host {
            case "today": session.selectedTab = 1
            case "new": session.showingComposer = true
            case "item":
                if let id = UUID(uuidString: url.lastPathComponent) { session.requestedItemID = id }
            default: session.selectedTab = 0
            }
        }
    }
}
