import SwiftUI

struct CalendarView: View {
    @Environment(AppSession.self) private var session
    @Environment(\.dynamicTypeSize) private var typeSize
    @State private var month = Date()
    @State private var selectedDay = Calendar.current.startOfDay(for: Date())
    @State private var includeCompleted = false
    @State private var showingComposer = false
    @State private var snoozing: InboxItem?
    @State private var choosingDay = false
    private var calendar: Calendar { .current }
    private var entries: [ScheduledEntry] {
        session.items.map { ScheduledEntry(id: $0.id, dueDate: $0.dueDate, status: $0.status) }
    }
    private var selectedItems: [InboxItem] {
        let ids = CalendarSchedule.identifiers(entries, on: selectedDay, completed: includeCompleted, calendar: calendar)
        let values = Dictionary(session.items.map { ($0.id, $0) }, uniquingKeysWith: { first, _ in first })
        return ids.compactMap { values[$0] }
    }
    var body: some View {
        TimelineView(.periodic(from: .now, by: 60)) { timeline in
            let model = CalendarMonth(containing: month, calendar: calendar)
            let counts = CalendarSchedule.counts(entries, in: month, completed: includeCompleted, calendar: calendar)
            List {
                Section {
                    monthControls
                    if typeSize.isAccessibilitySize {
                        BoxActionButton(title: "日付を選ぶ：" + selectedDay.formatted(.dateTime.month().day()),
                                        symbol: "calendar", identifier: "calendarChooseDayButton") { choosingDay = true }
                    } else {
                        ScrollView(.horizontal) {
                            VStack(spacing: 8) {
                                HStack(spacing: 2) {
                                    ForEach(model.weekdayLabels.indices, id: \.self) { index in
                                        Text(model.weekdayLabels[index]).font(.caption).frame(maxWidth: .infinity).accessibilityHidden(true)
                                    }
                                }
                                LazyVGrid(columns: Array(repeating: GridItem(.flexible(minimum: 44), spacing: 2), count: 7), spacing: 4) {
                                    ForEach(0..<model.leadingEmptyDays, id: \.self) { _ in Color.clear.frame(height: 1).accessibilityHidden(true) }
                                    ForEach(model.days) { day in dayButton(day, count: counts[day.date] ?? 0, now: timeline.date, compact: true) }
                                }
                            }.frame(minWidth: 320)
                        }.scrollIndicators(.hidden)
                    }
                    Text("数字の下は項目の件数です。日付を押すと、その日の内容を確認できます。")
                        .font(.footnote).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
                    BoxActionButton(title: "完了した項目：" + (includeCompleted ? "表示する" : "表示しない"),
                                    symbol: includeCompleted ? "checkmark.square" : "square", identifier: "calendarCompletedToggle") {
                        includeCompleted.toggle()
                    }
                }
                Section {
                    BoxActionButton(title: "この日に追加", symbol: "calendar.badge.plus", identifier: "calendarAddButton") {
                        showingComposer = true
                    }
                    if selectedItems.isEmpty {
                        Text("この日の項目はありません").foregroundStyle(.secondary).accessibilityIdentifier("calendarEmptyDay")
                    }
                    ForEach(selectedItems) { item in
                        ItemCard(item: item, now: timeline.date, complete: { session.complete(item) }, snooze: { snoozing = item })
                    }
                } header: {
                    Text(selectedDay, format: .dateTime.month().day().weekday(.wide))
                        .accessibilityIdentifier("calendarSelectedDate")
                }
                let undated = session.items.filter { $0.dueDate == nil && $0.status.isOpen }
                if !undated.isEmpty {
                    Section("日付未設定（\(undated.count)件）") {
                        ForEach(undated) { item in
                            ItemCard(item: item, now: timeline.date, complete: { session.complete(item) }, snooze: { snoozing = item })
                        }
                    }
                }
            }
        }
        .navigationTitle("カレンダー").navigationBarTitleDisplayMode(.inline)
        .sheet(isPresented: $showingComposer) {
            NavigationStack { ComposeView(initialDueDate: CalendarSchedule.dateForNewItem(on: selectedDay)) }
        }
        .sheet(item: $snoozing) { item in SnoozeSheet(item: item) }
        .sheet(isPresented: $choosingDay) {
            NavigationStack {
                List(CalendarMonth(containing: month, calendar: calendar).days) { day in
                    BoxActionButton(title: day.date.formatted(.dateTime.month().day().weekday(.wide)),
                                    symbol: calendar.isDate(day.date, inSameDayAs: selectedDay) ? "checkmark.circle" : "calendar",
                                    identifier: "calendarDay_\(day.number)") { selectedDay = day.date; choosingDay = false }
                }
                .navigationTitle("日付を選ぶ").navigationBarTitleDisplayMode(.inline)
                .toolbar { ToolbarItem(placement: .cancellationAction) { Button("閉じる") { choosingDay = false } } }
            }
        }
    }
    private var monthControls: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(month, format: .dateTime.year().month(.wide)).font(.headline).accessibilityIdentifier("calendarMonthTitle")
            ViewThatFits(in: .horizontal) {
                HStack(spacing: 8) { monthButtons }
                VStack(alignment: .leading, spacing: 8) { monthButtons }
            }
        }
    }
    @ViewBuilder private var monthButtons: some View {
        BoxActionButton(title: "前の月", symbol: "chevron.left", identifier: "calendarPreviousMonth") { changeMonth(-1) }
        BoxActionButton(title: "今日", symbol: "calendar", identifier: "calendarTodayButton") {
            month = Date(); selectedDay = calendar.startOfDay(for: Date())
        }
        BoxActionButton(title: "次の月", symbol: "chevron.right", identifier: "calendarNextMonth") { changeMonth(1) }
    }
    private func changeMonth(_ amount: Int) {
        guard let date = calendar.date(byAdding: .month, value: amount, to: CalendarMonth(containing: month).start) else { return }
        month = date; selectedDay = calendar.startOfDay(for: date)
    }
    private func dayButton(_ day: CalendarDay, count: Int, now: Date, compact: Bool) -> some View {
        let selected = calendar.isDate(day.date, inSameDayAs: selectedDay)
        let today = calendar.isDate(day.date, inSameDayAs: now)
        return Button { selectedDay = day.date } label: {
            Group {
                if compact {
                    VStack(spacing: 4) {
                        Text("\(day.number)").font(.body.weight(selected ? .bold : .regular))
                        Text("\(count)件").font(.caption)
                        if today { Text("今日").font(.caption2.bold()) }
                        else if selected { Image(systemName: "checkmark").font(.caption2).accessibilityHidden(true) }
                    }.frame(maxWidth: .infinity, minHeight: 76)
                } else {
                    HStack(alignment: .top) {
                        Text(day.date, format: .dateTime.month().day().weekday(.wide)).fixedSize(horizontal: false, vertical: true)
                        Spacer()
                        VStack(alignment: .trailing) {
                            Text("\(count)件")
                            if today { Text("今日") }
                            if selected { Label("選択中", systemImage: "checkmark") }
                        }
                    }.frame(minHeight: 44)
                }
            }
            .padding(4).foregroundStyle(.primary)
            .background(selected ? Color.boxAccent.opacity(0.12) : Color.clear, in: RoundedRectangle(cornerRadius: 8))
            .overlay { RoundedRectangle(cornerRadius: 8).stroke(selected ? Color.boxAccent : Color.clear, lineWidth: 2) }
        }
        .buttonStyle(.plain)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(day.date.formatted(.dateTime.year().month().day().weekday(.wide)) + "、\(count)件" + (today ? "、今日" : ""))
        .accessibilityAddTraits(selected ? [.isSelected] : [])
        .accessibilityHint("この日の項目を表示します")
        .accessibilityIdentifier("calendarDay_\(day.number)")
    }
}
