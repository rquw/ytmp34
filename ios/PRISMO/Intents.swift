import AppIntents

enum AskMode: String, AppEnum {
    case jetzt, zuege, heim, heute, morgen, notiz

    static var typeDisplayRepresentation: TypeDisplayRepresentation = "Frage"
    static var caseDisplayRepresentations: [AskMode: DisplayRepresentation] = [
        .jetzt: DisplayRepresentation(title: "Nächster Schritt", image: .init(systemName: "arrow.right.circle.fill")),
        .zuege: DisplayRepresentation(title: "Züge nach Linz", image: .init(systemName: "tram.fill")),
        .heim: DisplayRepresentation(title: "Wie komm ich heim?!", image: .init(systemName: "house.fill")),
        .heute: DisplayRepresentation(title: "Heute", image: .init(systemName: "calendar")),
        .morgen: DisplayRepresentation(title: "Morgen", image: .init(systemName: "moon.stars.fill")),
        .notiz: DisplayRepresentation(title: "Sprachnotiz", image: .init(systemName: "mic.fill")),
    ]
}

// the action button: asks what you want, answers in the popup, app stays closed
struct AskPrismo: AppIntent, ForegroundContinuableIntent {
    static var title: LocalizedStringResource = "PRISMO fragen"
    static var openAppWhenRun = false

    @Parameter(title: "Was?", requestValueDialog: "Was willst du wissen?")
    var mode: AskMode

    func perform() async throws -> some IntentResult & ProvidesDialog {
        if mode == .notiz {
            // recording needs the app on screen: open it straight into the recorder
            throw needsToContinueInForegroundError("Sprachnotiz") {
                await MainActor.run { Voice.shared.startRequested = true }
            }
        }
        let loc = await Tracker.shared.currentLocation()
        let text = await API.ask(mode.rawValue, loc)
        return .result(dialog: IntentDialog(stringLiteral: text))
    }
}

struct NextStep: AppIntent {
    static var title: LocalizedStringResource = "PRISMO: Was jetzt?"
    static var openAppWhenRun = false

    func perform() async throws -> some IntentResult & ProvidesDialog {
        let loc = await Tracker.shared.currentLocation()
        return .result(dialog: IntentDialog(stringLiteral: await API.ask("jetzt", loc)))
    }
}

// for the 05:50 automation: makes sure today's alarm matches cancelled periods and trains
struct UpdateAlarm: AppIntent {
    static var title: LocalizedStringResource = "PRISMO: Wecker aktualisieren"
    static var openAppWhenRun = false

    func perform() async throws -> some IntentResult & ProvidesDialog {
        return .result(dialog: IntentDialog(stringLiteral: await Alarms.refresh()))
    }
}

struct VoiceNote: AppIntent {
    static var title: LocalizedStringResource = "PRISMO: Sprachnotiz"
    static var openAppWhenRun = true

    @MainActor
    func perform() async throws -> some IntentResult {
        Voice.shared.startRequested = true
        return .result()
    }
}

struct PrismoShortcuts: AppShortcutsProvider {
    static var appShortcuts: [AppShortcut] {
        AppShortcut(intent: AskPrismo(), phrases: ["\(.applicationName) fragen", "Frag \(.applicationName)"],
                    shortTitle: "PRISMO fragen", systemImageName: "questionmark.circle.fill")
        AppShortcut(intent: NextStep(), phrases: ["Was jetzt \(.applicationName)"],
                    shortTitle: "Was jetzt?", systemImageName: "arrow.right.circle.fill")
        AppShortcut(intent: VoiceNote(), phrases: ["\(.applicationName) Notiz", "Sprachnotiz \(.applicationName)"],
                    shortTitle: "Sprachnotiz", systemImageName: "mic.fill")
        AppShortcut(intent: UpdateAlarm(), phrases: ["\(.applicationName) Wecker"],
                    shortTitle: "Wecker aktualisieren", systemImageName: "alarm.fill")
    }
}
