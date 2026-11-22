import SwiftUI
import CoreLocation

@main
struct PrismoApp: App {
    @Environment(\.scenePhase) private var phase

    init() {
        _ = Tracker.shared  // region events relaunch the app in the background: be ready for them
    }

    var body: some Scene {
        WindowGroup {
            Home()
                .preferredColorScheme(.dark)
                .onAppear { Tracker.shared.start() }
        }
        .onChange(of: phase) { _, p in
            if p == .active { Task { await Alarms.refresh() } }
        }
    }
}

struct Home: View {
    @ObservedObject private var tracker = Tracker.shared
    @State private var text = ""
    @State private var mode = "jetzt"
    @State private var loading = false
    @State private var alarms = Alarms.scheduled

    private let modes: [(String, String)] = [
        ("jetzt", "arrow.right.circle.fill"), ("zuege", "tram.fill"), ("heim", "house.fill"),
        ("heute", "calendar"), ("morgen", "moon.stars.fill"),
    ]

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Text("PRISMO").font(.system(size: 15, weight: .heavy, design: .monospaced)).tracking(3)
                Spacer()
                status
            }
            .padding(.horizontal, 20).padding(.top, 8)

            ScrollView {
                VStack(alignment: .leading, spacing: 10) {
                    let lines = text.components(separatedBy: "\n")
                    if loading && text.isEmpty {
                        ProgressView().frame(maxWidth: .infinity).padding(.top, 60)
                    }
                    ForEach(Array(lines.enumerated()), id: \.offset) { i, line in
                        Text(line)
                            .font(i == 0 ? .system(size: 26, weight: .bold) : .system(size: 18, weight: .regular))
                            .foregroundStyle(i == 0 ? .white : (line.hasPrefix("danach") ? .secondary : .white.opacity(0.85)))
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }
                }
                .padding(20)
                .opacity(loading ? 0.5 : 1)
            }
            .refreshable { await load() }

            HStack(spacing: 0) {
                ForEach(modes, id: \.0) { m in
                    Button {
                        mode = m.0
                        Task { await load() }
                    } label: {
                        Image(systemName: m.1)
                            .font(.system(size: 24, weight: .semibold))
                            .frame(maxWidth: .infinity, minHeight: 64)
                            .foregroundStyle(mode == m.0 ? Color.purple : Color.white.opacity(0.55))
                    }
                }
            }
            .background(.ultraThinMaterial)
        }
        .task { await load() }
    }

    private var status: some View {
        HStack(spacing: 10) {
            if let next = alarms.keys.sorted().first, let t = alarms[next] {
                Label(t, systemImage: "alarm.fill").font(.system(size: 13, weight: .semibold, design: .monospaced))
            }
            Image(systemName: tracker.auth == .authorizedAlways ? "location.fill" : "location.slash.fill")
                .foregroundStyle(tracker.auth == .authorizedAlways ? Color.green : Color.orange)
                .font(.system(size: 13))
        }
        .foregroundStyle(.secondary)
    }

    private func load() async {
        loading = true
        let loc = await Tracker.shared.currentLocation()
        text = await API.ask(mode, loc)
        alarms = Alarms.scheduled
        loading = false
    }
}
