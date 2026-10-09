import SwiftUI
import SwiftData

struct BoxView: View {
    @Environment(AppSession.self) private var session
    private var items: [InboxItem] { session.items }
    @State private var snoozing: InboxItem?
    @Environment(\.dynamicTypeSize) private var typeSize

    var body: some View {
        TimelineView(.periodic(from: .now, by: 60)) { timeline in
            let openItems = items.filter { $0.status.isOpen }
            List {
                if typeSize.isAccessibilitySize {
                    BoxActionButton(title: "追加", symbol: "plus", identifier: "addButton") {
                        session.showingComposer = true
                    }
                }
                if openItems.isEmpty {
                    VStack(spacing: 16) {
                        EmptyBoxState(title: "箱はすっきり", symbol: "tray",
                            message: "「あとでやろう」をここへ。\nメモや写真から、ひとつ追加してみましょう。")
                        if !typeSize.isAccessibilitySize {
                            BoxActionButton(title: "追加する", symbol: "plus", prominent: true, identifier: "emptyAddButton") {
                                session.showingComposer = true
                            }
                        }
                    }.listRowBackground(Color.clear)
                }
                ForEach(InboxSection.allCases) { section in
                    let group = openItems.filter { InboxSection.section(for: $0, now: timeline.date) == section }
                        .sorted { ($0.dueDate ?? .distantFuture) < ($1.dueDate ?? .distantFuture) }
                    if !group.isEmpty {
                        Section {
                            ForEach(group) { item in
                                ItemCard(item: item, now: timeline.date, complete: { session.complete(item) },
                                         snooze: { snoozing = item })
                            }
                        } header: {
                            Label("\(section.label) · \(group.count)", systemImage: section.symbol)
                                .foregroundStyle(section == .overdue ? Color.red : Color.primary)
                        }
                    }
                }
            }
        }
        .navigationTitle("箱")
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                if !typeSize.isAccessibilitySize {
                    Button { session.showingComposer = true } label: { BoxActionLabel(title: "追加", symbol: "plus") }
                        .buttonStyle(BoxActionButtonStyle()).accessibilityIdentifier("addButton")
                }
            }
        }
        .sheet(item: $snoozing) { item in SnoozeSheet(item: item) }
    }
}

/// Full-height text inside the scrollable list, with no truncation at larger sizes.
struct EmptyBoxState: View {
    let title: String
    let symbol: String
    let message: String
    var body: some View {
        VStack(spacing: 12) {
            Image(systemName: symbol).font(.largeTitle).foregroundStyle(Color.boxAccent).accessibilityHidden(true)
            BoxStatusText(text: title, headline: true, identifier: "emptyStateTitle",
                textStyle: .title2, centered: true, background: .clear)
            BoxStatusText(text: message, identifier: "emptyStateMessage", centered: true, background: .clear)
        }
        .foregroundStyle(.primary).multilineTextAlignment(.center)
        .frame(maxWidth: .infinity).padding(.vertical, 24)
        .accessibilityElement(children: .contain)
    }
}
