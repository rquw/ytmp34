import Foundation
import SwiftUI
import AlarmKit

struct PrismoAlarm: AlarmMetadata {}

// real alarms, set by PRISMO for the next school days. refreshed whenever the app gets a chance
// (opening it, coming home, the 05:50 automation), so even a week without the app still rings
enum Alarms {
    static let idsKey = "alarmIDs"

    static var scheduled: [String: String] {  // date -> time, for the screen
        get { UserDefaults.standard.dictionary(forKey: "alarmPlan") as? [String: String] ?? [:] }
        set { UserDefaults.standard.set(newValue, forKey: "alarmPlan") }
    }

    @discardableResult
    static func refresh() async -> String {
        let m = AlarmManager.shared
        if m.authorizationState != .authorized {
            guard (try? await m.requestAuthorization()) == .authorized else { return "⏰ Wecker nicht erlaubt" }
        }
        guard let plan = try? await API.alarms() else { return "PRISMO antwortet nicht, Wecker bleibt wie er ist" }

        for s in UserDefaults.standard.stringArray(forKey: idsKey) ?? [] {
            if let id = UUID(uuidString: s) { try? m.cancel(id: id) }
        }
        var ids: [String] = []
        var shown: [String: String] = [:]
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd HH:mm"
        f.timeZone = TimeZone(identifier: "Europe/Vienna")
        for w in plan where !w.alarm.isEmpty {
            guard let date = f.date(from: "\(w.date) \(w.alarm)"), date > Date() else { continue }
            let stop = AlarmButton(text: "Aus", textColor: .white, systemImageName: "sun.max.fill")
            let alert = AlarmPresentation.Alert(title: LocalizedStringResource(stringLiteral: w.why.isEmpty ? "PRISMO" : w.why),
                                                stopButton: stop)
            let attrs = AlarmAttributes<PrismoAlarm>(presentation: AlarmPresentation(alert: alert), tintColor: .purple)
            let id = UUID()
            let config = AlarmManager.AlarmConfiguration<PrismoAlarm>(schedule: .fixed(date), attributes: attrs)
            if (try? await m.schedule(id: id, configuration: config)) != nil {
                ids.append(id.uuidString)
                shown[w.date] = w.alarm
            }
        }
        UserDefaults.standard.set(ids, forKey: idsKey)
        scheduled = shown
        UserDefaults.standard.set(Date(), forKey: "alarmsUpdated")
        if let next = shown.keys.sorted().first, let t = shown[next] {
            return "⏰ nächster Wecker \(t) (\(next.suffix(5)))"
        }
        return "⏰ kein Wecker nötig"
    }
}
