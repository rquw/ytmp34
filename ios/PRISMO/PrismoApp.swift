import SwiftUI
import CoreLocation

import UserNotifications

// background uploads (voice notes) wake the app through here, and pushes also show while the app is open
final class AppDelegate: NSObject, UIApplicationDelegate, UNUserNotificationCenterDelegate {
    func application(_ application: UIApplication,
                     didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil) -> Bool {
        UNUserNotificationCenter.current().delegate = self
        return true
    }

    func application(_ application: UIApplication, handleEventsForBackgroundURLSession identifier: String,
                     completionHandler: @escaping () -> Void) {
        Uploader.shared.finished = completionHandler
        _ = Uploader.shared.session
    }

    func userNotificationCenter(_ center: UNUserNotificationCenter, willPresent notification: UNNotification)
        async -> UNNotificationPresentationOptions {
        [.banner, .sound]
    }
}

@main
struct PrismoApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
    @Environment(\.scenePhase) private var phase
    @ObservedObject private var voice = Voice.shared
    @State private var showVoice = false

    init() {
        _ = Tracker.shared  // region events relaunch the app in the background: be ready for them
        _ = Uploader.shared.session  // picks up voice notes still uploading from last time
    }

    var body: some Scene {
        WindowGroup {
            TabView {
                Tab("Planer", systemImage: "figure.walk.departure") { PlannerView() }
                Tab("Stundenplan", systemImage: "calendar") { TimetableView() }
                Tab("Status", systemImage: "cpu") { StatusView() }
            }
            .tint(.purple)
            .preferredColorScheme(.dark)
            .onAppear { Tracker.shared.start() }
            .overlay(alignment: .bottomTrailing) {
                // voice note: one button, everywhere in the app
                Button { showVoice = true } label: {
                    Image(systemName: "mic.fill").font(.system(size: 22, weight: .bold)).foregroundStyle(.white)
                        .frame(width: 58, height: 58)
                        .background(Circle().fill(Color.purple).shadow(color: .purple.opacity(0.5), radius: 10))
                }
                .padding(.trailing, 20).padding(.bottom, 96)
            }
            .sheet(isPresented: $showVoice) { VoiceView().presentationDetents([.large]) }
            .onChange(of: voice.startRequested) { _, go in
                if go {
                    showVoice = true
                    voice.startRequested = false
                }
            }
        }
        .onChange(of: phase) { _, p in
            if p == .active { Task { await Alarms.refresh() } }
        }
    }
}

// --- shared bits ---

struct TitleBar: View {
    let title: String
    @ObservedObject private var tracker = Tracker.shared
    var alarms: [String: String] = Alarms.scheduled

    var body: some View {
        HStack {
            Text(title).font(.system(size: 15, weight: .heavy, design: .monospaced)).tracking(3)
            Spacer()
            if let next = alarms.keys.sorted().first, let t = alarms[next] {
                Label(t, systemImage: "alarm.fill").font(.system(size: 13, weight: .semibold, design: .monospaced))
                    .foregroundStyle(.secondary)
            }
            Image(systemName: tracker.auth == .authorizedAlways ? "location.fill" : "location.slash.fill")
                .foregroundStyle(tracker.auth == .authorizedAlways ? Color.green : Color.orange)
                .font(.system(size: 13))
        }
        .padding(.horizontal, 20).padding(.top, 8)
    }
}

struct TextCard: View {
    let text: String
    let loading: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            if loading && text.isEmpty {
                ProgressView().frame(maxWidth: .infinity).padding(.top, 60)
            }
            ForEach(Array(text.components(separatedBy: "\n").enumerated()), id: \.offset) { i, line in
                Text(line)
                    .font(i == 0 ? .system(size: 24, weight: .bold) : .system(size: 17))
                    .foregroundStyle(i == 0 ? .white : (line.hasPrefix("danach") || line.hasPrefix(" ") ? .secondary : .white.opacity(0.85)))
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
        .padding(20)
        .opacity(loading ? 0.5 : 1)
    }
}

// --- planner: what now, trains, home, tomorrow ---

struct PlannerView: View {
    @State private var text = ""
    @State private var mode = "jetzt"
    @State private var loading = false
    @State private var alarms = Alarms.scheduled

    private let modes: [(String, String, String)] = [
        ("jetzt", "arrow.right.circle.fill", "Nächster Schritt"), ("nachlinz", "tram.fill", "Züge nach Linz"),
        ("heim", "house.fill", "Wie komm ich heim?!"), ("morgen", "moon.stars.fill", "Morgen"),
    ]

    var body: some View {
        VStack(spacing: 0) {
            TitleBar(title: "PLANER", alarms: alarms)
            LazyVGrid(columns: [GridItem(.flexible(), spacing: 8), GridItem(.flexible(), spacing: 8)], spacing: 8) {
                ForEach(modes, id: \.0) { m in
                    Button {
                        mode = m.0
                        Task { await load() }
                    } label: {
                        HStack(spacing: 8) {
                            Image(systemName: m.1).font(.system(size: 18, weight: .semibold)).frame(width: 24)
                            Text(m.2).font(.system(size: 14, weight: .semibold)).lineLimit(1).minimumScaleFactor(0.8)
                            Spacer(minLength: 0)
                        }
                        .padding(.horizontal, 12)
                        .frame(maxWidth: .infinity, minHeight: 50)
                        .background(RoundedRectangle(cornerRadius: 14)
                            .fill(mode == m.0 ? Color.purple.opacity(0.55) : Color.white.opacity(0.07)))
                        .foregroundStyle(.white)
                    }
                }
            }
            .padding(.horizontal, 20).padding(.vertical, 12)
            ScrollView { TextCard(text: text, loading: loading) }
                .refreshable { await load() }
        }
        .task { await load() }
    }

    private func load() async {
        loading = true
        let loc = await Tracker.shared.currentLocation()
        text = await API.ask(mode, loc)
        alarms = Alarms.scheduled
        loading = false
    }
}

// --- timetable: every day untis knows, with the plan for it ---

struct TimetableView: View {
    @State private var days: [API.Day] = []
    @State private var picked = ""
    @State private var text = ""
    @State private var loading = false

    var body: some View {
        VStack(spacing: 0) {
            TitleBar(title: "STUNDENPLAN")
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 8) {
                    ForEach(days) { d in
                        Button {
                            picked = d.date
                            Task { await load() }
                        } label: {
                            VStack(spacing: 3) {
                                Text(d.label).font(.system(size: 15, weight: .bold))
                                Text(d.free ? "frei" : d.first).font(.system(size: 12, design: .monospaced))
                                    .foregroundStyle(d.first != "07:45" && !d.free ? Color.green : Color.secondary)
                            }
                            .frame(width: 62, height: 54)
                            .background(RoundedRectangle(cornerRadius: 12)
                                .fill(picked == d.date ? Color.purple.opacity(0.55) : Color.white.opacity(0.07)))
                            .overlay(alignment: .topTrailing) {
                                if d.changed { Circle().fill(Color.orange).frame(width: 8, height: 8).padding(6) }
                            }
                            .foregroundStyle(.white)
                        }
                    }
                }
                .padding(.horizontal, 20).padding(.vertical, 10)
            }
            ScrollView { TextCard(text: text, loading: loading) }
                .refreshable {
                    days = await API.days()
                    await load()
                }
        }
        .task {
            if days.isEmpty { days = await API.days() }
            if picked.isEmpty { picked = days.first(where: { !$0.free })?.date ?? days.first?.date ?? "" }
            await load()
        }
    }

    private func load() async {
        guard !picked.isEmpty else {
            text = "Untis hat noch keine Tage"
            return
        }
        loading = true
        text = await API.day(picked)
        loading = false
    }
}
