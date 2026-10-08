import Foundation
import CoreLocation

@MainActor
final class LocationReminderService: NSObject, CLLocationManagerDelegate {
    private let manager = CLLocationManager()
    var authorizationChanged: (() -> Void)?
    override init() { super.init(); manager.delegate = self }
    var status: CLAuthorizationStatus { manager.authorizationStatus }

    func requestWhenInUse() throws {
        guard CLLocationManager.isMonitoringAvailable(for: CLCircularRegion.self) else { throw AppError.locationUnavailable }
        switch manager.authorizationStatus {
        case .notDetermined: manager.requestWhenInUseAuthorization()
        case .denied, .restricted: throw AppError.locationDenied
        default: break
        }
    }
    func requestBackgroundForReminder() throws {
        guard CLLocationManager.isMonitoringAvailable(for: CLCircularRegion.self) else { throw AppError.locationUnavailable }
        switch manager.authorizationStatus {
        case .authorizedWhenInUse: manager.requestAlwaysAuthorization()
        case .authorizedAlways: break
        default: throw AppError.locationDenied
        }
    }
    nonisolated func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        Task { @MainActor [weak self] in self?.authorizationChanged?() }
    }
    // No startUpdatingLocation: coordinates come from a user-selected point on the map.
}
