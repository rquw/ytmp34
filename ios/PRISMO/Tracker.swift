import Foundation
import CoreLocation
import UserNotifications

// the checkpoints: ios watches a few circles (home, stations, school) for free and wakes the app when
// one is crossed. leaving a station turns on gps for a few minutes to see if he's moving at train speed.
final class Tracker: NSObject, CLLocationManagerDelegate, ObservableObject {
    static let shared = Tracker()

    private let lm = CLLocationManager()
    @Published var auth: CLAuthorizationStatus = .notDetermined
    @Published var watching: [String] = []

    private var boostUntil = Date.distantPast
    private var boostFrom = ""
    private var fastSamples = 0
    private var reported = false
    private var activity: CLBackgroundActivitySession?
    private var oneShot: [CheckedContinuation<CLLocation?, Never>] = []

    override init() {
        super.init()
        lm.delegate = self
        lm.desiredAccuracy = kCLLocationAccuracyHundredMeters
        lm.pausesLocationUpdatesAutomatically = false
        auth = lm.authorizationStatus
        watching = lm.monitoredRegions.map { $0.identifier }.sorted()
    }

    func start() {
        if lm.authorizationStatus == .notDetermined {
            lm.requestWhenInUseAuthorization()
        } else if lm.authorizationStatus == .authorizedWhenInUse {
            lm.requestAlwaysAuthorization()
        }
        UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound, .badge]) { _, _ in }
        Task { await setupRegions() }
    }

    func setupRegions() async {
        guard let places = try? await API.places() else { return }
        for r in lm.monitoredRegions { lm.stopMonitoring(for: r) }
        for (name, p) in places {
            let region = CLCircularRegion(center: CLLocationCoordinate2D(latitude: p.lat, longitude: p.lon),
                                          radius: max(100, p.r), identifier: name)
            region.notifyOnEntry = true
            region.notifyOnExit = true
            lm.startMonitoring(for: region)
        }
        await MainActor.run { self.watching = places.keys.sorted() }
    }

    // --- region crossings ---

    func locationManager(_ manager: CLLocationManager, didEnterRegion region: CLRegion) {
        let name = region.identifier
        Task {
            await API.event(name + "_arrive")
            if name == "hbf" { await linzNotification() }
            if name == "home" { await Alarms.refresh() }
        }
    }

    func locationManager(_ manager: CLLocationManager, didExitRegion region: CLRegion) {
        let name = region.identifier
        Task { await API.event(name + "_leave") }
        if name == "bf" || name == "schulen" { boost(from: name) }
    }

    // left a station: gps for 4 minutes. 3 readings faster than 30 km/h = on the train (or bus)
    private func boost(from name: String) {
        boostFrom = name
        boostUntil = Date().addingTimeInterval(240)
        fastSamples = 0
        reported = false
        activity = CLBackgroundActivitySession()
        lm.allowsBackgroundLocationUpdates = true
        lm.desiredAccuracy = kCLLocationAccuracyBest
        lm.startUpdatingLocation()
    }

    private func stopBoost() {
        lm.stopUpdatingLocation()
        lm.desiredAccuracy = kCLLocationAccuracyHundredMeters
        activity?.invalidate()
        activity = nil
    }

    func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        if let l = locations.last, !oneShot.isEmpty {
            let waiting = oneShot
            oneShot = []
            waiting.forEach { $0.resume(returning: l) }
        }
        guard Date() < boostUntil else {
            if activity != nil { stopBoost() }
            return
        }
        for l in locations where l.speed > 8.5 && l.horizontalAccuracy < 80 {
            fastSamples += 1
        }
        if fastSamples >= 3 && !reported {
            reported = true
            Task { await API.event("train_on") }
            stopBoost()
        }
    }

    func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {
        let waiting = oneShot
        oneShot = []
        waiting.forEach { $0.resume(returning: nil) }
    }

    func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        let s = manager.authorizationStatus
        DispatchQueue.main.async { self.auth = s }
        if s == .authorizedWhenInUse { manager.requestAlwaysAuthorization() }
    }

    // where am i right now (for the button)
    func currentLocation() async -> CLLocation? {
        if let l = lm.location, l.timestamp.timeIntervalSinceNow > -60 { return l }
        return await withCheckedContinuation { c in
            oneShot.append(c)
            lm.requestLocation()
            DispatchQueue.main.asyncAfter(deadline: .now() + 6) { [weak self] in
                guard let self, !self.oneShot.isEmpty else { return }
                let waiting = self.oneShot
                self.oneShot = []
                waiting.forEach { $0.resume(returning: self.lm.location) }
            }
        }
    }

    // arrived in linz: which tram, on time? straight from the app, no shortcut needed
    func linzNotification() async {
        let text = await API.ask("linz", nil)
        guard !text.isEmpty, !text.hasPrefix("Nix los") else { return }
        let c = UNMutableNotificationContent()
        let lines = text.components(separatedBy: "\n")
        c.title = lines.first ?? "Linz"
        c.body = lines.dropFirst().joined(separator: "\n")
        c.sound = .default
        c.interruptionLevel = .timeSensitive
        try? await UNUserNotificationCenter.current().add(UNNotificationRequest(identifier: "linz", content: c, trigger: nil))
    }
}
