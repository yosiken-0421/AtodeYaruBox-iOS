import SwiftUI
import UIKit

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
                    BoxActionButton(title: "日付を選ぶ：" + selectedDay.formatted(.dateTime.month().day()),
                                    symbol: "calendar", identifier: "calendarChooseDayButton") { choosingDay = true }
                    // Keep the same scalable date controls when the system changes
                    // text size. The ordinary list button is available at every size.
                    let font = UIFont.preferredFont(forTextStyle: .body,
                        compatibleWith: UITraitCollection(preferredContentSizeCategory: BoxTypography.category(typeSize)))
                    let dayWidth = max(44, font.pointSize * 2.5)
                        ScrollView(.horizontal) {
                            VStack(spacing: 8) {
                                HStack(spacing: 2) {
                                    ForEach(model.weekdayLabels.indices, id: \.self) { index in
                                        BoxStatusText(text: model.weekdayLabels[index], identifier: "calendarWeekday_\(index)",
                                            textStyle: .caption1, centered: true, background: .systemBackground)
                                            .frame(maxWidth: .infinity).accessibilityHidden(true)
                                    }
                                }
                                VStack(spacing: 4) {
                                    // A month has at most six rows. Keep all date controls
                                    // alive while text size changes or the user scrolls.
                                    ForEach(0..<((model.leadingEmptyDays + model.days.count + 6) / 7), id: \.self) { row in
                                        HStack(spacing: 2) {
                                            ForEach(0..<7, id: \.self) { column in
                                                let index = row * 7 + column - model.leadingEmptyDays
                                                if model.days.indices.contains(index) {
                                                    let day = model.days[index]
                                                    CalendarDayButton(number: day.number, count: counts[day.date] ?? 0,
                                                        today: calendar.isDate(day.date, inSameDayAs: timeline.date),
                                                        selected: calendar.isDate(day.date, inSameDayAs: selectedDay),
                                                        spokenDate: day.date.formatted(.dateTime.year().month().day().weekday(.wide))) {
                                                        selectedDay = day.date
                                                    }.frame(width: dayWidth)
                                                } else {
                                                    Color.clear.frame(width: dayWidth, height: 1).accessibilityHidden(true)
                                                }
                                            }
                                        }
                                    }
                                }
                            }.frame(minWidth: dayWidth * 7 + 12)
                        }.scrollIndicators(.hidden)
                    BoxStatusText(text: "数字の下は項目の件数です。日付を押すと、その日の内容を確認できます。",
                                  identifier: "calendarHelp", textStyle: .footnote)
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
                        BoxStatusText(text: "この日の項目はありません", identifier: "calendarEmptyDay")
                    }
                    ForEach(selectedItems) { item in
                        ItemCard(item: item, now: timeline.date, complete: { session.complete(item) }, snooze: { snoozing = item })
                    }
                } header: {
                    BoxStatusText(text: selectedDay.formatted(.dateTime.month().day().weekday(.wide)), headline: true,
                                  identifier: "calendarSelectedDate", background: .systemGroupedBackground)
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
            BoxStatusText(text: month.formatted(.dateTime.year().month(.wide)), headline: true,
                          identifier: "calendarMonthTitle", background: .systemBackground)
            HStack(spacing: 8) { monthButtons }
        }
    }
    @ViewBuilder private var monthButtons: some View {
        BoxActionButton(title: "前月", symbol: "chevron.left", identifier: "calendarPreviousMonth", hint: "前の月を表示します") { changeMonth(-1) }
        BoxActionButton(title: "今日", symbol: "calendar", identifier: "calendarTodayButton") {
            month = Date(); selectedDay = calendar.startOfDay(for: Date())
        }
        BoxActionButton(title: "翌月", symbol: "chevron.right", identifier: "calendarNextMonth", hint: "次の月を表示します") { changeMonth(1) }
    }
    private func changeMonth(_ amount: Int) {
        guard let date = calendar.date(byAdding: .month, value: amount, to: CalendarMonth(containing: month).start) else { return }
        month = date; selectedDay = calendar.startOfDay(for: date)
    }
}
