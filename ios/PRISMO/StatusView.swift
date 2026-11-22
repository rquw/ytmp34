import SwiftUI

// PRISMO's status, the same data as pie mode on the ytmp34 site. refreshes every 3 s while it's open
struct StatusView: View {
    @State private var d: [String: Any] = [:]
    @State private var error = ""
    @State private var morse = ""
    @State private var ledReply = ""

    private var pi: [String: Any] { d["pi"] as? [String: Any] ?? [:] }
    private var oracle: [String: Any] { d["oracle"] as? [String: Any] ?? [:] }

    var body: some View {
        VStack(spacing: 0) {
            TitleBar(title: "STATUS")
            ScrollView {
                VStack(alignment: .leading, spacing: 22) {
                    if !error.isEmpty && d.isEmpty {
                        Label(error, systemImage: "wifi.exclamationmark").foregroundStyle(.orange)
                    }
                    prismoSection
                    servicesSection
                    watchdogSection
                    ledSection
                    oracleSection
                    planesSection
                }
                .padding(20)
            }
        }
        .task {
            while !Task.isCancelled {
                await load()
                try? await Task.sleep(for: .seconds(3))
            }
        }
    }

    // --- sections ---

    private var prismoSection: some View {
        let online = !pi.isEmpty
        let mem = pi["memory"] as? [String: Any] ?? [:]
        let total = num(mem["total"]), avail = num(mem["available"])
        let disk = pi["disk"] as? [String: Any] ?? [:]
        let wifi = pi["wifi"] as? [String: Any] ?? [:]
        return VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 10) {
                Circle().fill(online ? Color.green : Color.red).frame(width: 12, height: 12)
                    .shadow(color: online ? .green : .red, radius: 6)
                Text("PRISMO").font(.system(size: 26, weight: .heavy))
                Spacer()
                if online { Text(duration(num(pi["uptime"]))).font(.system(size: 14, design: .monospaced)).foregroundStyle(.secondary) }
            }
            if !online {
                Text((d["pi_error"] as? String) ?? "offline").foregroundStyle(.red).font(.system(size: 14))
            }
            LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 10), count: 3), spacing: 10) {
                tile("thermometer.medium", String(format: "%.0f°", num(pi["cpu_temp"])), num(pi["cpu_temp"]) > 70 ? .orange : .white)
                tile("cpu", String(format: "%.0f%%", num(pi["cpu"])), .white)
                tile("memorychip", total > 0 ? String(format: "%.0f%%", 100 * (1 - avail / total)) : "?", .white)
                tile("wifi", wifi["dbm"] != nil ? String(format: "%.0f", num(wifi["dbm"])) : "?", num(wifi["dbm"]) < -75 ? .orange : .white)
                tile("internaldrive", String(format: "%.1fG", num(disk["free"]) / 1e9), .white)
                tile("bolt", pi["volts"] != nil ? String(format: "%.2fV", num(pi["volts"])) : "?", .white)
            }
        }
    }

    private var servicesSection: some View {
        let svc = (pi["services"] as? [String: String] ?? [:]).sorted { $0.key < $1.key }
        let names = ["ytmp34": "Converter", "ytmp34-proxy": "Proxy", "untis-watch.timer": "Untis", "tailscaled": "Tailscale",
                     "ytmp34-update.timer": "Update", "prismo-watchdog": "Wachhund", "prismo-briefing.timer": "Briefing",
                     "prismo-scan": "Scanner", "prismo-day": "Tagesplan"]
        return section("gearshape.2.fill") {
            FlowRow(items: svc.map { ($0.key, names[$0.key] ?? $0.key, $0.value == "active") })
        }
    }

    private var watchdogSection: some View {
        let sites = ((pi["prismo"] as? [String: Any])?["sites"] as? [String: [String: Any]] ?? [:]).sorted { $0.key < $1.key }
        return section("dog.fill") {
            ForEach(sites, id: \.key) { name, s in
                HStack {
                    Circle().fill((s["ok"] as? Bool ?? false) ? Color.green : Color.red).frame(width: 8, height: 8)
                    Text(name).font(.system(size: 15))
                    Spacer()
                    if let took = s["took"] { Text(String(format: "%.0f ms", num(took) * 1000)).font(.system(size: 13, design: .monospaced)).foregroundStyle(.secondary) }
                }
            }
        }
    }

    private var ledSection: some View {
        section("lightbulb.fill") {
            HStack(spacing: 10) {
                ledButton("heart.fill", "heartbeat")
                ledButton("light.beacon.max.fill", "blink")
                TextField("Morse", text: $morse)
                    .textFieldStyle(.plain).padding(10)
                    .background(RoundedRectangle(cornerRadius: 10).fill(Color.white.opacity(0.07)))
                    .onSubmit { led("morse", morse) }
            }
            if !ledReply.isEmpty { Text(ledReply).font(.system(size: 13)).foregroundStyle(.secondary) }
        }
    }

    private var oracleSection: some View {
        let mem = oracle["memory"] as? [String: Any] ?? [:]
        let total = num(mem["total"]), avail = num(mem["available"])
        let tot = oracle["totals"] as? [String: Any] ?? [:]
        let q = oracle["queue"] as? [String: Any] ?? [:]
        return section("cloud.fill") {
            LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 10), count: 3), spacing: 10) {
                tile("cpu", String(format: "%.0f%%", num(oracle["cpu"])), .white)
                tile("memorychip", total > 0 ? String(format: "%.0f%%", 100 * (1 - avail / total)) : "?", .white)
                tile("person.2.fill", "\(Int(num(oracle["active"])))", .white)
                tile("music.note", "\(Int(num(tot["videos"])))", .white)
                tile("hourglass", "\(Int(num(q["running"])))/\(Int(num(q["waiting"])))", .white)
                tile("play.rectangle.fill", (oracle["youtube_ok"] as? Bool ?? false) ? "ok" : "!", (oracle["youtube_ok"] as? Bool ?? false) ? .green : .red)
            }
        }
    }

    private var planesSection: some View {
        let p = pi["planes"] as? [String: Any] ?? [:]
        let list = p["list"] as? [[String: Any]] ?? []
        return section("airplane") {
            HStack {
                Text("\(Int(num(p["today"]))) heute").font(.system(size: 15, weight: .semibold))
                Spacer()
            }
            ForEach(Array(list.prefix(5).enumerated()), id: \.offset) { _, a in
                HStack {
                    Text((a["cs"] as? String ?? a["reg"] as? String ?? "?").trimmingCharacters(in: .whitespaces))
                        .font(.system(size: 14, design: .monospaced))
                    Text(a["type"] as? String ?? "").font(.system(size: 13)).foregroundStyle(.secondary).lineLimit(1)
                    Spacer()
                    Text(String(format: "%.1f km", num(a["dist"]))).font(.system(size: 13, design: .monospaced)).foregroundStyle(.secondary)
                }
            }
        }
    }

    // --- pieces ---

    private func section<C: View>(_ icon: String, @ViewBuilder _ content: () -> C) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Image(systemName: icon).font(.system(size: 16, weight: .bold)).foregroundStyle(.purple)
            content()
        }
    }

    private func tile(_ icon: String, _ value: String, _ color: Color) -> some View {
        VStack(spacing: 6) {
            Image(systemName: icon).font(.system(size: 15)).foregroundStyle(.secondary)
            Text(value).font(.system(size: 18, weight: .bold, design: .monospaced)).foregroundStyle(color)
                .minimumScaleFactor(0.6).lineLimit(1)
        }
        .frame(maxWidth: .infinity, minHeight: 64)
        .background(RoundedRectangle(cornerRadius: 12).fill(Color.white.opacity(0.06)))
    }

    private func ledButton(_ icon: String, _ action: String) -> some View {
        Button { led(action, "") } label: {
            Image(systemName: icon).font(.system(size: 18)).frame(width: 46, height: 42)
                .background(RoundedRectangle(cornerRadius: 10).fill(Color.purple.opacity(0.4)))
                .foregroundStyle(.white)
        }
    }

    private func led(_ action: String, _ text: String) {
        Task {
            let data = try? await API.get("/scan/led", ["action": action, "text": text], timeout: 10)
            let j = (data.flatMap { try? JSONSerialization.jsonObject(with: $0) } as? [String: Any]) ?? [:]
            ledReply = (j["error"] as? String) ?? (j["ok"] != nil ? "💡" : "")
            if action == "morse" { morse = "" }
        }
    }

    private func load() async {
        do {
            let data = try await API.get("/scan/status", [:], timeout: 10)
            if let j = try JSONSerialization.jsonObject(with: data) as? [String: Any] {
                d = j
                error = ""
            }
        } catch {
            self.error = "Oracle antwortet nicht"
        }
    }

    private func num(_ v: Any?) -> Double {
        if let n = v as? NSNumber { return n.doubleValue }
        if let s = v as? String { return Double(s) ?? 0 }
        return 0
    }

    private func duration(_ s: Double) -> String {
        let d = Int(s) / 86400, h = Int(s) % 86400 / 3600, m = Int(s) % 3600 / 60
        return d > 0 ? "\(d)d \(h)h" : h > 0 ? "\(h)h \(m)m" : "\(m)m"
    }
}

struct FlowRow: View {
    let items: [(String, String, Bool)]

    var body: some View {
        LazyVGrid(columns: [GridItem(.adaptive(minimum: 100), spacing: 8)], alignment: .leading, spacing: 8) {
            ForEach(items, id: \.0) { _, label, ok in
                HStack(spacing: 6) {
                    Circle().fill(ok ? Color.green : Color.red).frame(width: 7, height: 7)
                    Text(label).font(.system(size: 13, weight: .medium)).lineLimit(1)
                }
                .padding(.horizontal, 10).padding(.vertical, 7)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(Capsule().fill(Color.white.opacity(0.07)))
            }
        }
    }
}
