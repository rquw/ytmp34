import SwiftUI
import AVFoundation
import EventKit
import UserNotifications

// hold to talk, let go, put the phone away. the upload runs in a background session,
// iOS wakes the app when oracle answers, then the reminders get saved and a push says so
@MainActor
final class Voice: ObservableObject {
    static let shared = Voice()

    @Published var recording = false
    @Published var level: Float = 0
    @Published var problem = ""
    @Published var startRequested = false

    private var recorder: AVAudioRecorder?
    private var meter: Timer?
    private var started = Date()
    private let file = FileManager.default.temporaryDirectory.appendingPathComponent("recording.m4a")

    func start() {
        guard !recording else { return }
        problem = ""
        Task {
            guard await AVAudioApplication.requestRecordPermission() else {
                problem = "Mikrofon nicht erlaubt (Einstellungen → PRISMO)"
                return
            }
            _ = try? await UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound])
            do {
                let s = AVAudioSession.sharedInstance()
                try s.setCategory(.record, mode: .default)
                try s.setActive(true)
                let r = try AVAudioRecorder(url: file, settings: [
                    AVFormatIDKey: kAudioFormatMPEG4AAC, AVSampleRateKey: 22050, AVNumberOfChannelsKey: 1,
                    AVEncoderAudioQualityKey: AVAudioQuality.medium.rawValue])
                r.isMeteringEnabled = true
                r.record(forDuration: 120)
                recorder = r
                started = Date()
                recording = true
                UIImpactFeedbackGenerator(style: .medium).impactOccurred()
                meter = Timer.scheduledTimer(withTimeInterval: 0.05, repeats: true) { _ in
                    Task { @MainActor in
                        guard let r = Voice.shared.recorder else { return }
                        r.updateMeters()
                        Voice.shared.level = max(0, (r.averagePower(forChannel: 0) + 50) / 50)
                    }
                }
            } catch {
                problem = error.localizedDescription
            }
        }
    }

    // returns true if something was sent
    @discardableResult
    func stop() -> Bool {
        guard recording else { return false }
        meter?.invalidate()
        recorder?.stop()
        recorder = nil
        recording = false
        level = 0
        try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)
        guard Date().timeIntervalSince(started) > 0.7 else {
            UINotificationFeedbackGenerator().notificationOccurred(.warning)
            problem = "Länger halten"
            return false
        }
        // own copy per note, so the next recording can't overwrite one that's still uploading
        let dir = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask)[0]
        let note = dir.appendingPathComponent("note-\(UUID().uuidString).m4a")
        do {
            try FileManager.default.moveItem(at: file, to: note)
        } catch {
            problem = error.localizedDescription
            return false
        }
        Uploader.shared.send(note)
        UINotificationFeedbackGenerator().notificationOccurred(.success)
        return true
    }
}

final class Uploader: NSObject, URLSessionDataDelegate {
    static let shared = Uploader()
    static let id = "at.fabiosch.prismo.voice"
    var finished: (() -> Void)?
    private var buffers: [Int: Data] = [:]
    private var files: [Int: URL] = [:]
    private let lock = NSLock()

    lazy var session: URLSession = {
        let c = URLSessionConfiguration.background(withIdentifier: Uploader.id)
        c.sessionSendsLaunchEvents = true
        c.isDiscretionary = false
        c.timeoutIntervalForResource = 600
        return URLSession(configuration: c, delegate: self, delegateQueue: nil)
    }()

    func send(_ note: URL) {
        var req = URLRequest(url: API.url("/ai/voice"))
        req.httpMethod = "POST"
        req.setValue("audio/mp4", forHTTPHeaderField: "Content-Type")
        req.setValue("note.m4a", forHTTPHeaderField: "X-Filename")
        let task = session.uploadTask(with: req, fromFile: note)
        task.taskDescription = note.path
        task.resume()
    }

    func urlSession(_ session: URLSession, dataTask: URLSessionDataTask, didReceive data: Data) {
        lock.lock()
        buffers[dataTask.taskIdentifier, default: Data()].append(data)
        lock.unlock()
    }

    func urlSession(_ session: URLSession, task: URLSessionTask, didCompleteWithError error: Error?) {
        lock.lock()
        let data = buffers.removeValue(forKey: task.taskIdentifier) ?? Data()
        lock.unlock()
        if let path = task.taskDescription { try? FileManager.default.removeItem(atPath: path) }
        let code = (task.response as? HTTPURLResponse)?.statusCode ?? 0
        Task {
            if let error {
                await Uploader.notify("❌ Sprachnotiz ging nicht durch", error.localizedDescription)
            } else if code != 200 {
                let msg = (try? JSONSerialization.jsonObject(with: data) as? [String: Any])?["error"] as? String
                await Uploader.notify("❌ Sprachnotiz ging nicht durch", msg ?? "Fehler \(code)")
            } else {
                await Uploader.handle(data)
            }
        }
    }

    func urlSessionDidFinishEvents(forBackgroundURLSession session: URLSession) {
        DispatchQueue.main.async {
            self.finished?()
            self.finished = nil
        }
    }

    struct Answer: Decodable {
        struct R: Decodable { let title: String; let due: String?; let notes: String? }
        let text: String
        let reminders: [R]
    }

    static func handle(_ data: Data) async {
        guard let a = try? JSONDecoder().decode(Answer.self, from: data) else {
            await notify("❌ Sprachnotiz ging nicht durch", "Komische Antwort von PRISMO")
            return
        }
        if a.reminders.isEmpty {
            await notify("🤷 Nix zum Merken gehört", a.text.isEmpty ? "Da war nur Stille" : "„\(a.text)“")
            return
        }
        let store = EKEventStore()
        guard (try? await store.requestFullAccessToReminders()) == true else {
            await notify("❌ Erinnerungen nicht erlaubt", "Einstellungen → PRISMO → Erinnerungen")
            return
        }
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd'T'HH:mm"
        f.timeZone = TimeZone(identifier: "Europe/Vienna")
        let show = DateFormatter()
        show.dateFormat = "E HH:mm"
        show.locale = Locale(identifier: "de_AT")
        var lines: [String] = []
        do {
            for item in a.reminders {
                let r = EKReminder(eventStore: store)
                r.title = item.title
                r.notes = (item.notes?.isEmpty == false) ? item.notes : nil
                r.calendar = store.defaultCalendarForNewReminders()
                var line = item.title
                if let due = item.due.flatMap({ f.date(from: $0) }) {
                    r.dueDateComponents = Calendar.current.dateComponents([.year, .month, .day, .hour, .minute], from: due)
                    r.addAlarm(EKAlarm(absoluteDate: due))
                    line += "  " + show.string(from: due)
                }
                try store.save(r, commit: false)
                lines.append(line)
            }
            try store.commit()
        } catch {
            await notify("❌ Erinnerungen nicht gespeichert", error.localizedDescription)
            return
        }
        let n = a.reminders.count
        await notify(n == 1 ? "✅ Erinnerung gespeichert" : "✅ \(n) Erinnerungen gespeichert", lines.joined(separator: "\n"))
    }

    static func notify(_ title: String, _ body: String) async {
        let c = UNMutableNotificationContent()
        c.title = title
        c.body = body
        c.sound = .default
        c.interruptionLevel = .timeSensitive
        try? await UNUserNotificationCenter.current().add(
            UNNotificationRequest(identifier: UUID().uuidString, content: c, trigger: nil))
    }
}

struct VoiceView: View {
    @ObservedObject private var v = Voice.shared
    @Environment(\.dismiss) private var dismiss
    @State private var pressing = false

    var body: some View {
        VStack(spacing: 30) {
            Spacer()
            ZStack {
                Circle().fill((v.recording ? Color.red : Color.purple).opacity(0.25))
                    .frame(width: 190 + CGFloat(v.level) * 70, height: 190 + CGFloat(v.level) * 70)
                    .animation(.easeOut(duration: 0.1), value: v.level)
                Circle().fill(v.recording ? Color.red : Color.purple).frame(width: 150, height: 150)
                    .scaleEffect(pressing ? 0.92 : 1)
                    .animation(.spring(duration: 0.2), value: pressing)
                Image(systemName: v.recording ? "waveform" : "mic.fill")
                    .font(.system(size: 54, weight: .bold)).foregroundStyle(.white)
                    .symbolEffect(.variableColor.iterative, isActive: v.recording)
            }
            .contentShape(Circle())
            .gesture(
                DragGesture(minimumDistance: 0)
                    .onChanged { _ in
                        if !pressing {
                            pressing = true
                            v.start()
                        }
                    }
                    .onEnded { _ in
                        pressing = false
                        // the permission prompt can still be up: give start() a moment to land
                        Task {
                            try? await Task.sleep(for: .milliseconds(150))
                            if v.stop() { dismiss() }
                        }
                    }
            )
            Group {
                if !v.problem.isEmpty {
                    Text(v.problem).foregroundStyle(.orange)
                } else if v.recording {
                    Image(systemName: "hand.raised.fill").foregroundStyle(.red)
                } else {
                    Image(systemName: "hand.tap.fill").foregroundStyle(.secondary)
                }
            }
            .font(.system(size: 22, weight: .semibold))
            .multilineTextAlignment(.center)
            Spacer()
        }
        .padding(24)
        .preferredColorScheme(.dark)
        .onAppear { v.problem = "" }
    }
}
