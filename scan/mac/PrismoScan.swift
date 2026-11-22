// PRISMO scan for the Mac: sits in the menu bar, keeps one quiet connection to oracle open
// and opens whatever PRISMO scans. links and text go to Chrome, pictures to Preview.
// built by install.sh, no Xcode project needed.
import Cocoa

let server = "https://132-226-199-122.sslip.io"
let keyFile = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent(".config/prismo-scan/key")

struct Scan: Decodable { let id: Int; let text: String; let type: String; let at: Double; let to: String? }
struct Scans: Decodable { let scans: [Scan] }

func symbol(_ name: String, _ size: CGFloat = 15) -> NSImage? {
    let img = NSImage(systemSymbolName: name, accessibilityDescription: nil)
    return img?.withSymbolConfiguration(.init(pointSize: size, weight: .medium))
}

func isImage(_ t: String) -> Bool {
    if t.hasPrefix("data:image/") { return true }
    guard let u = URL(string: t), u.scheme?.hasPrefix("http") == true else { return false }
    return ["png", "jpg", "jpeg", "gif", "webp", "heic", "bmp"].contains(u.pathExtension.lowercased())
}

func isLink(_ t: String) -> Bool {
    let l = t.lowercased()
    return l.hasPrefix("http://") || l.hasPrefix("https://") || l.hasPrefix("www.")
}

func icon(for s: Scan) -> String {
    if isImage(s.text) { return "photo" }
    if isLink(s.text) { return "link" }
    if s.type != "QR-Code" && s.type != "TEST" { return "barcode" }
    return "text.alignleft"
}

final class App: NSObject, NSApplicationDelegate, NSPopoverDelegate {
    var item: NSStatusItem!
    let popover = NSPopover()
    var key = ""
    let dev: String
    let session: URLSession
    var gen = 0
    var backoff = 2.0
    var camTimer: Timer?
    var camBusy = false
    let cam = NSImageView()
    let rows = NSStackView()
    var recent: [Scan] = []

    override init() {
        let d = UserDefaults.standard
        if d.string(forKey: "dev") == nil { d.set(UUID().uuidString, forKey: "dev") }
        dev = d.string(forKey: "dev")!
        let c = URLSessionConfiguration.ephemeral
        c.timeoutIntervalForRequest = 45
        c.httpMaximumConnectionsPerHost = 2
        session = URLSession(configuration: c)
        super.init()
    }

    func applicationDidFinishLaunching(_ n: Notification) {
        item = NSStatusBar.system.statusItem(withLength: NSStatusItem.squareLength)
        item.button?.image = symbol("qrcode.viewfinder")
        item.button?.image?.isTemplate = true
        item.button?.action = #selector(toggle)
        item.button?.target = self
        buildPopover()
        NSWorkspace.shared.notificationCenter.addObserver(self, selector: #selector(woke),
                                                          name: NSWorkspace.didWakeNotification, object: nil)
        key = (try? String(contentsOf: keyFile, encoding: .utf8))?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        if key.isEmpty { askKey() } else { poll() }
    }

    // --- the long-poll: one request open, oracle answers when there's a scan or after 25 s ---

    func idleSeconds() -> Double {
        CGEventSource.secondsSinceLastEventType(.combinedSessionState, eventType: CGEventType(rawValue: ~0)!)
    }

    func poll() {
        gen += 1
        let mine = gen
        var c = URLComponents(string: server + "/scan/wait")!
        c.queryItems = [.init(name: "dev", value: dev), .init(name: "kind", value: "mac"),
                        .init(name: "name", value: Host.current().localizedName ?? "Mac"),
                        .init(name: "idle", value: String(Int(idleSeconds())))]
        var r = URLRequest(url: c.url!)
        r.setValue(key, forHTTPHeaderField: "X-Scan-Key")
        session.dataTask(with: r) { data, resp, err in
            DispatchQueue.main.async { if mine == self.gen { self.got(data, resp as? HTTPURLResponse) } }
        }.resume()
    }

    func got(_ data: Data?, _ resp: HTTPURLResponse?) {
        if resp?.statusCode == 403 {
            item.button?.appearsDisabled = true
            return askKey()
        }
        guard resp?.statusCode == 200, let data = data, let s = try? JSONDecoder().decode(Scans.self, from: data) else {
            item.button?.appearsDisabled = true
            let wait = backoff
            backoff = min(backoff * 2, 60)
            let mine = gen
            DispatchQueue.main.asyncAfter(deadline: .now() + wait) { if mine == self.gen { self.poll() } }
            return
        }
        item.button?.appearsDisabled = false
        backoff = 2
        for scan in s.scans { open(scan); flash() }
        poll()
    }

    @objc func woke() { backoff = 2; poll() }

    // --- opening things ---

    func open(_ s: Scan) {
        let t = s.text.trimmingCharacters(in: .whitespacesAndNewlines)
        if isImage(t) { return showImage(t) }
        var url: URL?
        if isLink(t) {
            url = URL(string: t.lowercased().hasPrefix("www.") ? "https://" + t : t)
        }
        if url == nil {
            var c = URLComponents(string: "https://www.google.com/search")!
            c.queryItems = [.init(name: "q", value: t)]
            url = c.url
        }
        guard let u = url else { return }
        let ws = NSWorkspace.shared
        if let chrome = ws.urlForApplication(withBundleIdentifier: "com.google.Chrome") {
            ws.open([u], withApplicationAt: chrome, configuration: NSWorkspace.OpenConfiguration())
        } else {
            ws.open(u)
        }
    }

    func showImage(_ t: String) {
        let dir = FileManager.default.temporaryDirectory.appendingPathComponent("prismo-scan", isDirectory: true)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        let preview = { (file: URL) in
            let ws = NSWorkspace.shared
            if let app = ws.urlForApplication(withBundleIdentifier: "com.apple.Preview") {
                ws.open([file], withApplicationAt: app, configuration: NSWorkspace.OpenConfiguration())
            } else { ws.open(file) }
        }
        if t.hasPrefix("data:image/"), let comma = t.firstIndex(of: ",") {
            let ext = t.dropFirst(11).prefix { $0 != ";" && $0 != "," }
            guard let data = Data(base64Encoded: String(t[t.index(after: comma)...])) else { return }
            let file = dir.appendingPathComponent("scan-\(Int(Date().timeIntervalSince1970)).\(ext.isEmpty ? "png" : String(ext))")
            try? data.write(to: file)
            return preview(file)
        }
        guard let u = URL(string: t) else { return }
        session.downloadTask(with: u) { tmp, _, _ in
            guard let tmp = tmp else { return }
            let file = dir.appendingPathComponent("scan-\(Int(Date().timeIntervalSince1970)).\(u.pathExtension)")
            try? FileManager.default.moveItem(at: tmp, to: file)
            DispatchQueue.main.async { preview(file) }
        }.resume()
    }

    func flash() {
        item.button?.image = symbol("checkmark.circle.fill")
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) { self.item.button?.image = symbol("qrcode.viewfinder") }
    }

    // --- the key, asked once ---

    func askKey() {
        let a = NSAlert()
        a.messageText = "PRISMO scan key"
        a.informativeText = "install-pi.sh prints it at the end"
        let f = NSTextField(frame: NSRect(x: 0, y: 0, width: 280, height: 24))
        f.stringValue = key
        a.accessoryView = f
        a.addButton(withTitle: "OK")
        a.addButton(withTitle: "Quit")
        NSApp.activate(ignoringOtherApps: true)
        a.window.initialFirstResponder = f
        if a.runModal() != .alertFirstButtonReturn { NSApp.terminate(nil) }
        key = f.stringValue.trimmingCharacters(in: .whitespacesAndNewlines)
        try? FileManager.default.createDirectory(at: keyFile.deletingLastPathComponent(), withIntermediateDirectories: true)
        try? key.write(to: keyFile, atomically: true, encoding: .utf8)
        try? FileManager.default.setAttributes([.posixPermissions: 0o600], ofItemAtPath: keyFile.path)
        poll()
    }

    // --- the window: live camera + recent scans, only alive while it's open ---

    func buildPopover() {
        let vc = NSViewController()
        let root = NSStackView()
        root.orientation = .vertical
        root.alignment = .leading
        root.spacing = 10
        root.edgeInsets = NSEdgeInsets(top: 12, left: 12, bottom: 10, right: 12)

        cam.imageScaling = .scaleProportionallyUpOrDown
        cam.wantsLayer = true
        cam.layer?.backgroundColor = NSColor.black.cgColor
        cam.layer?.cornerRadius = 8
        cam.translatesAutoresizingMaskIntoConstraints = false
        cam.widthAnchor.constraint(equalToConstant: 320).isActive = true
        cam.heightAnchor.constraint(equalToConstant: 240).isActive = true

        rows.orientation = .vertical
        rows.alignment = .leading
        rows.spacing = 2
        let scroll = NSScrollView()
        scroll.drawsBackground = false
        scroll.hasVerticalScroller = true
        let clip = FlippedView()
        clip.translatesAutoresizingMaskIntoConstraints = false
        clip.addSubview(rows)
        rows.translatesAutoresizingMaskIntoConstraints = false
        NSLayoutConstraint.activate([rows.topAnchor.constraint(equalTo: clip.topAnchor),
                                     rows.leadingAnchor.constraint(equalTo: clip.leadingAnchor),
                                     rows.trailingAnchor.constraint(equalTo: clip.trailingAnchor),
                                     rows.bottomAnchor.constraint(equalTo: clip.bottomAnchor)])
        scroll.documentView = clip
        clip.widthAnchor.constraint(equalTo: scroll.contentView.widthAnchor).isActive = true
        scroll.translatesAutoresizingMaskIntoConstraints = false
        scroll.widthAnchor.constraint(equalToConstant: 320).isActive = true
        scroll.heightAnchor.constraint(equalToConstant: 200).isActive = true

        let quit = NSButton(image: symbol("power", 13)!, target: NSApp, action: #selector(NSApplication.terminate(_:)))
        quit.isBordered = false
        quit.contentTintColor = .secondaryLabelColor
        let keyBtn = NSButton(image: symbol("key", 13)!, target: self, action: #selector(changeKey))
        keyBtn.isBordered = false
        keyBtn.contentTintColor = .secondaryLabelColor
        let bar = NSStackView(views: [keyBtn, NSView(), quit])
        bar.translatesAutoresizingMaskIntoConstraints = false
        bar.widthAnchor.constraint(equalToConstant: 320).isActive = true

        [cam, scroll, bar].forEach { root.addArrangedSubview($0) }
        vc.view = root
        popover.contentViewController = vc
        popover.behavior = .transient
        popover.delegate = self
    }

    @objc func toggle() {
        if popover.isShown { popover.performClose(nil); return }
        guard let b = item.button else { return }
        popover.show(relativeTo: b.bounds, of: b, preferredEdge: .minY)
        NSApp.activate(ignoringOtherApps: true)
    }

    @objc func changeKey() { popover.performClose(nil); askKey() }

    func popoverWillShow(_ n: Notification) {
        cam.image = symbol("eye.slash", 28)
        cam.contentTintColor = .darkGray
        loadRecent()
        camTimer = Timer.scheduledTimer(withTimeInterval: 0.35, repeats: true) { [weak self] _ in self?.frame() }
        frame()
    }

    func popoverDidClose(_ n: Notification) {
        camTimer?.invalidate()
        camTimer = nil
        cam.image = nil
    }

    func get(_ path: String, _ done: @escaping (Data?, Int) -> Void) {
        var r = URLRequest(url: URL(string: server + path)!)
        r.setValue(key, forHTTPHeaderField: "X-Scan-Key")
        r.timeoutInterval = 6
        session.dataTask(with: r) { d, resp, _ in
            let code = (resp as? HTTPURLResponse)?.statusCode ?? 0
            DispatchQueue.main.async { done(d, code) }
        }.resume()
    }

    func frame() {
        if camBusy { return }
        camBusy = true
        get("/scan/cam.jpg") { d, code in
            self.camBusy = false
            guard self.popover.isShown else { return }
            if code == 200, let d = d, let img = NSImage(data: d) { self.cam.image = img }
            else { self.cam.image = symbol("eye.slash", 28) }
        }
    }

    func loadRecent() {
        get("/scan/recent") { d, code in
            guard code == 200, let d = d, let s = try? JSONDecoder().decode(Scans.self, from: d) else { return }
            self.recent = s.scans
            self.rows.arrangedSubviews.forEach { $0.removeFromSuperview() }
            if s.scans.isEmpty {
                let none = NSImageView(image: symbol("tray", 22)!)
                none.contentTintColor = .tertiaryLabelColor
                self.rows.addArrangedSubview(none)
            }
            for (i, scan) in s.scans.enumerated() {
                let b = NSButton(title: scan.text.replacingOccurrences(of: "\n", with: " "),
                                 image: symbol(icon(for: scan), 13)!, target: self, action: #selector(self.reopen(_:)))
                b.tag = i
                b.isBordered = false
                b.imagePosition = .imageLeading
                b.alignment = .left
                b.lineBreakMode = .byTruncatingTail
                b.contentTintColor = .labelColor
                b.toolTip = scan.text
                let when = NSTextField(labelWithString: ago(scan.at))
                when.textColor = .tertiaryLabelColor
                when.font = .systemFont(ofSize: 11)
                let to = NSImageView(image: symbol(scan.to == nil ? "moon.zzz" : "checkmark", 10)!)
                to.contentTintColor = .tertiaryLabelColor
                to.toolTip = scan.to
                b.setContentCompressionResistancePriority(.defaultLow, for: .horizontal)
                let row = NSStackView(views: [b, NSView(), to, when])
                row.translatesAutoresizingMaskIntoConstraints = false
                row.widthAnchor.constraint(equalToConstant: 300).isActive = true
                self.rows.addArrangedSubview(row)
            }
        }
    }

    @objc func reopen(_ b: NSButton) {
        guard b.tag < recent.count else { return }
        popover.performClose(nil)
        open(recent[b.tag])
    }
}

func ago(_ t: Double) -> String {
    let s = Int(Date().timeIntervalSince1970 - t)
    if s < 60 { return "now" }
    if s < 3600 { return "\(s / 60)m" }
    if s < 86400 { return "\(s / 3600)h" }
    return "\(s / 86400)d"
}

final class FlippedView: NSView { override var isFlipped: Bool { true } }

let app = NSApplication.shared
let delegate = App()
app.delegate = delegate
app.setActivationPolicy(.accessory)
app.run()
