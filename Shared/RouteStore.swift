import Foundation

enum RouteStore {
    static let changed = Notification.Name("AtodeYaruBoxRouteChanged")
    private static var preferences: UserDefaults { UserDefaults(suiteName: SharedStore.groupID) ?? .standard }
    static func request(_ route: String) {
        preferences.set(route, forKey: "pendingRoute")
        preferences.set(Date().timeIntervalSince1970, forKey: "pendingRouteDate")
        NotificationCenter.default.post(name: changed, object: nil)
    }
    static func consume(now: Date = Date()) -> String? {
        guard let route = preferences.string(forKey: "pendingRoute") else { return nil }
        let date = preferences.double(forKey: "pendingRouteDate")
        preferences.removeObject(forKey: "pendingRoute")
        preferences.removeObject(forKey: "pendingRouteDate")
        guard now.timeIntervalSince1970 - date < 60 else { return nil }
        return route
    }
}
