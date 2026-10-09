import SwiftUI
import MapKit
import CoreLocation

struct LocationReminderView: View {
    let item: InboxItem
    @Environment(AppSession.self) private var session
    @Environment(\.dismiss) private var dismiss
    @State private var name = ""
    @State private var coordinate: CLLocationCoordinate2D?
    @State private var onEntry = true
    @State private var query = ""
    @State private var results: [MKMapItem] = []
    @State private var isSearching = false
    @State private var errorMessage: String?
    var body: some View {
        Form {
            Section("場所を選ぶ") {
                TextField("場所・住所", text: $query)
                Button {
                    isSearching = true
                    Task {
                        defer { isSearching = false }
                        do {
                            let request = MKLocalSearch.Request(); request.naturalLanguageQuery = query
                            results = try await MKLocalSearch(request: request).start().mapItems
                            if results.isEmpty { errorMessage = "場所が見つかりませんでした。住所でも検索できます。" }
                        } catch { errorMessage = "場所を検索できませんでした。通信状態を確認してください。" }
                    }
                } label: { Label("地図で場所を検索", systemImage: "magnifyingglass") }
                    .disabled(query.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || isSearching)
                Text("検索すると、入力した場所・住所がAppleの地図サービスに送信されます。現在地は送信しません。")
                    .font(.footnote).foregroundStyle(.secondary)
                ForEach(Array(results.enumerated()), id: \.offset) { _, result in
                    Button {
                        coordinate = coordinate(for: result)
                        name = result.name ?? query
                    } label: {
                        VStack(alignment: .leading) {
                            Text(result.name ?? "場所")
                            Text(address(for: result)).font(.footnote).foregroundStyle(.secondary)
                        }.frame(minHeight: 44)
                    }
                }
                if coordinate != nil { LabeledContent("選んだ場所", value: name) }
            }
            Section("お知らせのタイミング") {
                Picker("タイミング", selection: $onEntry) { Text("着いたら").tag(true); Text("出たら").tag(false) }
                Text("選んだ場所の約200m以内への出入りを、iPhoneの地域監視で検知します。位置を連続で記録しません。")
                    .font(.footnote).foregroundStyle(.secondary)
            }
            Section("位置情報の許可") {
                Button {
                    do { try session.location.requestWhenInUse() } catch { errorMessage = error.localizedDescription }
                } label: { Label("位置情報の利用を許可", systemImage: "location") }
                Button {
                    do { try session.location.requestBackgroundForReminder() } catch { errorMessage = error.localizedDescription }
                } label: { Label("アプリを閉じても知らせる", systemImage: "bell") }
                Text("場所で通知する場合だけ「常に」を許可してください。許可後に下の保存ボタンを押します。")
                    .font(.footnote).foregroundStyle(.secondary)
            }
            Section {
                Button {
                    Task {
                        do {
                            guard session.location.status == .authorizedAlways else { throw AppError.locationDenied }
                            guard let coordinate else { throw AppError.invalidLocation }
                            let location = LocationReminder(name: name, latitude: coordinate.latitude, longitude: coordinate.longitude, onEntry: onEntry)
                            guard location.isValid else { throw AppError.invalidLocation }
                            try session.repository.update(item) { $0.locationReminder = location }
                            await session.requestNotifications(); session.refreshSideEffects(); dismiss()
                        } catch { errorMessage = error.localizedDescription }
                    }
                } label: { Label("場所のお知らせを保存", systemImage: "checkmark").frame(minHeight: 44) }
                    .disabled(coordinate == nil)
            }
        }
        .navigationTitle("場所で知らせる").navigationBarTitleDisplayMode(.inline)
        .toolbar { Button("閉じる") { dismiss() } }
        .alert("お知らせ", isPresented: Binding(get: { errorMessage != nil }, set: { if !$0 { errorMessage = nil } })) {
            Button("閉じる", role: .cancel) { errorMessage = nil }
        } message: { Text(errorMessage ?? "") }
    }

    private func coordinate(for result: MKMapItem) -> CLLocationCoordinate2D {
        // Xcode 16 does not expose the iOS 26 MapKit members at compile time.
        #if compiler(>=6.2)
        if #available(iOS 26.0, *) { return result.location.coordinate }
        else { return result.placemark.coordinate }
        #else
        return result.placemark.coordinate
        #endif
    }

    private func address(for result: MKMapItem) -> String {
        #if compiler(>=6.2)
        if #available(iOS 26.0, *) { return result.address?.fullAddress ?? "" }
        else { return result.placemark.title ?? "" }
        #else
        return result.placemark.title ?? ""
        #endif
    }
}
