import SwiftUI
import SwiftData

struct SearchView: View {
    @Environment(AppSession.self) private var session
    private var items: [InboxItem] { session.items.sorted { $0.updatedAt > $1.updatedAt } }
    @State private var query = ""
    @State private var appliedQuery = ""
    @State private var filter: SearchFilter = .all
    @State private var snoozing: InboxItem?
    let searchFocus: FocusState<Bool>.Binding
    var body: some View {
        let results = items.filter { SearchEngine.matches($0, query: appliedQuery, filter: filter) }
        List {
            Section {
                VStack(alignment: .leading, spacing: 8) {
                    Label("検索", systemImage: "magnifyingglass").font(.headline).foregroundStyle(Color.primary)
                    TextField("検索する言葉", text: $query,
                        prompt: Text("検索する言葉").foregroundStyle(Color.primary))
                        .font(.body).foregroundStyle(Color.primary).textFieldStyle(.roundedBorder)
                        .autocorrectionDisabled().textInputAutocapitalization(.never)
                        .focused(searchFocus).submitLabel(.search)
                        .onSubmit { submitSearch() }
                        .frame(minHeight: 44).accessibilityIdentifier("searchField")
                    BoxActionButton(title: "検索する", symbol: "magnifyingglass", identifier: "searchSubmitButton",
                        hint: "入力した言葉で探し、キーボードを閉じます") { submitSearch() }
                }
            }
            Section {
                Picker("絞り込み", selection: $filter) {
                    ForEach(SearchFilter.allCases) { filter in Text(filter.label).tag(filter) }
                }.accessibilityIdentifier("searchFilter")
            }
            Section("\(results.count)件") {
                if results.isEmpty {
                    EmptyBoxState(title: "項目がありません", symbol: "magnifyingglass",
                        message: appliedQuery.isEmpty ? "保存した内容を、タイトル・メモ・読み取った文字から探せます。" : "言葉や絞り込みを変えて、もう一度探してみましょう。")
                } else {
                    ForEach(results) { item in
                        ItemCard(item: item, complete: { session.complete(item) }, snooze: { snoozing = item })
                    }
                }
            }
        }
        .navigationTitle("探す")
        .scrollDismissesKeyboard(.interactively)
        .onDisappear { searchFocus.wrappedValue = false }
        .task(id: query) {
            do { try await Task.sleep(for: .milliseconds(200)); appliedQuery = query }
            catch { /* A newer search replaces the previous one. */ }
        }
        .sheet(item: $snoozing) { item in SnoozeSheet(item: item) }
    }

    private func submitSearch() {
        appliedQuery = query
        searchFocus.wrappedValue = false
    }
}
