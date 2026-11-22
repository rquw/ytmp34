import SwiftUI
import AVFoundation
import EventKit

// voice note -> oracle (whisper + qwen) -> one iphone reminder per thing you said
@MainActor
final class Voice: ObservableObject {
    static let shared = Voice()

    enum Phase: Equatable { case idle, recording, thinking, done, failed(String) }
    @Published var phase: Phase = .idle
    @Published var level: Float = 0
    @Published var text = ""
    @Published var saved: [(String, Date?)] = []
    @Published var startRequested = false

    private var recorder: AVAudioRecorder?
    private var meter: Timer?
    private let store = EKEventStore()
    private let file = FileManager.default.temporaryDirectory.appendingPathComponent("note.m4a")

    func toggle() {
        if phase == .recording { stop() } else { Task { await start() } }
    }

    func start() async {
        guard await AVAudioApplication.requestRecordPermission() else {
            phase = .failed("Mikrofon nicht erlaubt (Einstellungen → PRISMO)")
            return
        }
        do {
            let s = AVAudioSession.sharedInstance()
            // .spokenAudio is a playback mode, with .record it throws -50
            try s.setCategory(.record, mode: .default)
            try s.setActive(true)
            let r = try AVAudioRecorder(url: file, settings: [
                AVFormatIDKey: kAudioFormatMPEG4AAC, AVSampleRateKey: 22050, AVNumberOfChannelsKey: 1,
                AVEncoderAudioQualityKey: AVAudioQuality.medium.rawValue])
            r.isMeteringEnabled = true
            r.record(forDuration: 120)
            recorder = r
            text = ""
            saved = []
            phase = .recording
            meter = Timer.scheduledTimer(withTimeInterval: 0.05, repeats: true) { [weak self] _ in
                Task { @MainActor in
                    guard let self, let r = self.recorder else { return }
                    r.updateMeters()
                    self.level = max(0, (r.averagePower(forChannel: 0) + 50) / 50)
                    if !r.isRecording && self.phase == .recording { self.stop() }
                }
            }
        } catch {
            phase = .failed(error.localizedDescription)
        }
    }

    func stop() {
        meter?.invalidate()
        recorder?.stop()
        recorder = nil
        try? AVAudioSession.sharedInstance().setActive(false)
        phase = .thinking
        Task { await send() }
    }

    struct Answer: Decodable {
        struct R: Decodable { let title: String; let due: String?; let notes: String? }
        let text: String
        let reminders: [R]
    }

    private func send() async {
        do {
            var req = URLRequest(url: API.url("/ai/voice"))
            req.httpMethod = "POST"
            req.timeoutInterval = 180
            req.setValue("audio/mp4", forHTTPHeaderField: "Content-Type")
            req.setValue("note.m4a", forHTTPHeaderField: "X-Filename")
            let (data, resp) = try await URLSession.shared.upload(for: req, fromFile: file)
            guard (resp as? HTTPURLResponse)?.statusCode == 200 else {
                throw NSError(domain: "PRISMO", code: 0, userInfo: [NSLocalizedDescriptionKey: String(data: data, encoding: .utf8) ?? "Fehler"])
            }
            let a = try JSONDecoder().decode(Answer.self, from: data)
            text = a.text
            try await save(a.reminders)
            phase = .done
        } catch {
            phase = .failed(error.localizedDescription)
        }
    }

    private func save(_ items: [Answer.R]) async throws {
        guard try await store.requestFullAccessToReminders() else {
            throw NSError(domain: "PRISMO", code: 0, userInfo: [NSLocalizedDescriptionKey: "Erinnerungen nicht erlaubt"])
        }
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd'T'HH:mm"
        f.timeZone = TimeZone(identifier: "Europe/Vienna")
        var out: [(String, Date?)] = []
        for item in items {
            let r = EKReminder(eventStore: store)
            r.title = item.title
            r.notes = (item.notes?.isEmpty == false) ? item.notes : nil
            r.calendar = store.defaultCalendarForNewReminders()
            let due = item.due.flatMap { f.date(from: $0) }
            if let due {
                r.dueDateComponents = Calendar.current.dateComponents([.year, .month, .day, .hour, .minute], from: due)
                r.addAlarm(EKAlarm(absoluteDate: due))
            }
            try store.save(r, commit: false)
            out.append((item.title, due))
        }
        try store.commit()
        saved = out
    }
}

struct VoiceView: View {
    @ObservedObject private var v = Voice.shared
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        VStack(spacing: 28) {
            Spacer()
            Button { v.toggle() } label: {
                ZStack {
                    Circle().fill(v.phase == .recording ? Color.red.opacity(0.25) : Color.purple.opacity(0.25))
                        .frame(width: 180 + CGFloat(v.level) * 60, height: 180 + CGFloat(v.level) * 60)
                        .animation(.easeOut(duration: 0.1), value: v.level)
                    Circle().fill(v.phase == .recording ? Color.red : Color.purple).frame(width: 140, height: 140)
                    Image(systemName: v.phase == .recording ? "stop.fill" : "mic.fill")
                        .font(.system(size: 50, weight: .bold)).foregroundStyle(.white)
                }
            }
            .disabled(v.phase == .thinking)

            Group {
                switch v.phase {
                case .idle: Text("Tippen und reden").foregroundStyle(.secondary)
                case .recording: Text("Ich hör zu …").foregroundStyle(.red)
                case .thinking: HStack(spacing: 10) { ProgressView(); Text("PRISMO denkt nach") }.foregroundStyle(.secondary)
                case .failed(let e): Text(e).foregroundStyle(.orange).multilineTextAlignment(.center)
                case .done: EmptyView()
                }
            }
            .font(.system(size: 17, weight: .semibold))

            if v.phase == .done {
                VStack(alignment: .leading, spacing: 12) {
                    if !v.text.isEmpty {
                        Text("„\(v.text)“").font(.system(size: 15)).foregroundStyle(.secondary)
                    }
                    if v.saved.isEmpty {
                        Label("Nix zum Merken gehört", systemImage: "questionmark.circle")
                    }
                    ForEach(Array(v.saved.enumerated()), id: \.offset) { _, r in
                        HStack(alignment: .top, spacing: 10) {
                            Image(systemName: "checkmark.circle.fill").foregroundStyle(.green)
                            VStack(alignment: .leading, spacing: 2) {
                                Text(r.0).font(.system(size: 17, weight: .semibold))
                                if let d = r.1 {
                                    Text(d.formatted(.dateTime.weekday(.abbreviated).day().month().hour().minute()))
                                        .font(.system(size: 13, design: .monospaced)).foregroundStyle(.secondary)
                                }
                            }
                        }
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(20)
                .background(RoundedRectangle(cornerRadius: 16).fill(Color.white.opacity(0.06)))
            }
            Spacer()
        }
        .padding(24)
        .preferredColorScheme(.dark)
        .onAppear {
            if v.phase != .recording && v.phase != .thinking { v.phase = .idle }
            if v.startRequested {
                v.startRequested = false
                Task { await v.start() }
            }
        }
    }
}
