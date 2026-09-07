import Cocoa
import WebKit

class AppDelegate: NSObject, NSApplicationDelegate {
    var statusItem: NSStatusItem!
    var window: NSWindow!
    var webView: WKWebView!
    var serverProcess: Process?

    func applicationDidFinishLaunching(_ aNotification: Notification) {
        // 1. Create Status Item in Menu Bar
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        if let button = statusItem.button {
            button.title = "⚡ U1-OS"
            button.action = #selector(toggleWindow)
            button.target = self
        }

        // 2. Setup WebKit Configuration
        let config = WKWebViewConfiguration()
        config.preferences.setValue(true, forKey: "developerExtrasEnabled")
        
        let screenFrame = NSScreen.main?.visibleFrame ?? NSRect(x: 0, y: 0, width: 1440, height: 900)
        let winWidth: CGFloat = min(1280, screenFrame.width - 80)
        let winHeight: CGFloat = min(840, screenFrame.height - 80)
        let winRect = NSRect(
            x: (screenFrame.width - winWidth) / 2,
            y: (screenFrame.height - winHeight) / 2,
            width: winWidth,
            height: winHeight
        )

        // 3. Setup Window
        window = NSWindow(
            contentRect: winRect,
            styleMask: [.titled, .closable, .miniaturizable, .resizable, .fullSizeContentView],
            backing: .buffered,
            defer: false
        )
        window.title = "Command Center OS — Sovereign Matrix"
        window.titlebarAppearsTransparent = true
        window.backgroundColor = NSColor(red: 0.03, green: 0.04, blue: 0.07, alpha: 1.0)
        window.isReleasedWhenClosed = false
        window.center()

        // 4. Create Web View
        webView = WKWebView(frame: winRect, configuration: config)
        webView.autoresizingMask = [.width, .height]
        window.contentView = webView

        // 5. Boot the localhost server if it is not already running.
        //    Wave 10: the app previously loaded a URL nothing was
        //    serving, so a cold double-click opened a blank window.
        startServerIfNeeded()

        // 6. Load Command Center URL (retrying while the server warms up)
        loadCommandCentre(attempt: 0)
    }

    /// Launches server.py from the bundled payload unless port 8787 already answers.
    func startServerIfNeeded() {
        if portIsOpen() { return }

        let fm = FileManager.default
        var root: String? = nil
        if let res = Bundle.main.resourcePath {
            if let stored = try? String(contentsOfFile: res + "/source_path", encoding: .utf8) {
                let trimmed = stored.trimmingCharacters(in: .whitespacesAndNewlines)
                if fm.fileExists(atPath: trimmed + "/server.py") { root = trimmed }
            }
            if root == nil, fm.fileExists(atPath: res + "/app/server.py") { root = res + "/app" }
        }
        guard let appRoot = root else { return }

        var python = "/usr/bin/python3"
        for candidate in ["/usr/bin/python3", "/opt/homebrew/bin/python3", "/usr/local/bin/python3"] {
            if fm.isExecutableFile(atPath: candidate) { python = candidate; break }
        }

        let task = Process()
        task.executableURL = URL(fileURLWithPath: python)
        task.arguments = ["server.py"]
        task.currentDirectoryURL = URL(fileURLWithPath: appRoot)
        let logPath = NSHomeDirectory() + "/Library/Logs/U1-OS.log"
        if !fm.fileExists(atPath: logPath) { fm.createFile(atPath: logPath, contents: nil) }
        if let handle = FileHandle(forWritingAtPath: logPath) {
            handle.seekToEndOfFile()
            task.standardOutput = handle
            task.standardError = handle
        }
        try? task.run()
        serverProcess = task
    }

    func portIsOpen() -> Bool {
        guard let url = URL(string: "http://127.0.0.1:8787/") else { return false }
        var request = URLRequest(url: url)
        request.timeoutInterval = 1.0
        var open = false
        let sem = DispatchSemaphore(value: 0)
        URLSession.shared.dataTask(with: request) { _, response, _ in
            if let http = response as? HTTPURLResponse, http.statusCode > 0 { open = true }
            sem.signal()
        }.resume()
        _ = sem.wait(timeout: .now() + 1.5)
        return open
    }

    /// Retries the initial load while the Python server finishes booting.
    func loadCommandCentre(attempt: Int) {
        guard let url = URL(string: "http://127.0.0.1:8787") else { return }
        if portIsOpen() || attempt > 40 {
            webView.load(URLRequest(url: url))
            return
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.4) { [weak self] in
            self?.loadCommandCentre(attempt: attempt + 1)
        }

        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    func applicationWillTerminate(_ aNotification: Notification) {
        serverProcess?.terminate()
    }

    @objc func toggleWindow() {
        if window.isVisible {
            window.orderOut(nil)
        } else {
            window.makeKeyAndOrderFront(nil)
            NSApp.activate(ignoringOtherApps: true)
        }
    }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.run()
