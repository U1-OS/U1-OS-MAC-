import AppKit
import WebKit
import ServiceManagement

final class U1Application: NSObject, NSApplicationDelegate, WKNavigationDelegate, WKUIDelegate, WKDownloadDelegate, URLSessionTaskDelegate {
    var window: NSWindow!
    var web: WKWebView!
    var launcher: Process?
    var timer: Timer?
    var attempts = 0
    var healthTask: URLSessionDataTask?
    var generation = 0
    var ready = false
    var sleeping = false
    var startedLauncher = false
    var needsReload = true
    var lastLocalURL = NavigationPolicy.base
    var externalPromptOpen = false
    let base = NavigationPolicy.base
    lazy var healthSession: URLSession = {
        let config = URLSessionConfiguration.ephemeral
        config.connectionProxyDictionary = [:]
        config.httpCookieStorage = nil
        config.urlCache = nil
        config.timeoutIntervalForResource = 3
        return URLSession(configuration: config, delegate: self, delegateQueue: nil)
    }()
    var root: String { Bundle.main.object(forInfoDictionaryKey: "U1WorkspaceRoot") as? String ?? "" }

    func applicationDidFinishLaunching(_ notification: Notification) {
        let config = WKWebViewConfiguration()
        config.websiteDataStore = .default()
        config.mediaTypesRequiringUserActionForPlayback = .all
        web = WKWebView(frame: .zero, configuration: config)
        web.navigationDelegate = self
        web.uiDelegate = self
        web.allowsBackForwardNavigationGestures = true
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1440, height: 950), styleMask: [.titled,.closable,.miniaturizable,.resizable], backing: .buffered, defer: false)
        window.title = "U1 OS"
        window.minSize = NSSize(width: 700, height: 620)
        window.isReleasedWhenClosed = false
        window.setFrameAutosaveName("U1WorkspaceWindow")
        window.backgroundColor = NSColor(calibratedRed: 0.025, green: 0.055, blue: 0.10, alpha: 1)
        window.contentView = web
        window.center()
        window.makeKeyAndOrderFront(nil)
        createMenu()
        let workspace = NSWorkspace.shared.notificationCenter
        workspace.addObserver(self, selector: #selector(willSleep), name: NSWorkspace.willSleepNotification, object: nil)
        workspace.addObserver(self, selector: #selector(didWake), name: NSWorkspace.didWakeNotification, object: nil)
        NSApp.activate(ignoringOtherApps: true)
        startWorkspace()
    }

    func cancelConnection() {
        generation += 1
        timer?.invalidate(); timer = nil
        healthTask?.cancel(); healthTask = nil
    }

    func scheduleChecks(every seconds: TimeInterval) {
        timer?.invalidate()
        timer = Timer.scheduledTimer(withTimeInterval: seconds, repeats: true) { [weak self] _ in self?.connect() }
    }

    func startWorkspace() {
        guard !sleeping else { return }
        cancelConnection()
        attempts = 0
        startedLauncher = false
        if !ready { statusPage("Connecting to your workspace", detail: "Checking your private local U1 OS installation.") }
        guard root.hasPrefix("/"), FileManager.default.fileExists(atPath: root + "/start-u1-os.command") else {
            statusPage("Installation path is missing", detail: "Rebuild the desktop application from your U1 OS workspace.")
            return
        }
        scheduleChecks(every: 0.75)
        connect()
    }

    func launchWorkspaceIfNeeded() {
        guard !startedLauncher, launcher?.isRunning != true else { return }
        startedLauncher = true
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/bin/bash")
        process.arguments = [root + "/start-u1-os.command", "--no-browser"]
        process.currentDirectoryURL = URL(fileURLWithPath: root)
        process.standardOutput = FileHandle.nullDevice
        process.standardError = FileHandle.nullDevice
        launcher = process
        do { try process.run() } catch {
            cancelConnection()
            statusPage("The workspace could not start", detail: "Use Help > Show Workspace, then open start-u1-os.command for details.")
        }
    }

    func connect() {
        guard !sleeping, healthTask == nil else { return }
        let requestGeneration = generation
        attempts += 1
        // Health identity remains readable while Safety protects all workspace
        // APIs. A locked healthy installation must load its canonical unlock UI.
        var request = URLRequest(url: base.appendingPathComponent("healthz"))
        request.timeoutInterval = 2
        request.cachePolicy = .reloadIgnoringLocalCacheData
        healthTask = healthSession.dataTask(with: request) { [weak self] data, response, _ in
            DispatchQueue.main.async {
                guard let self = self, requestGeneration == self.generation, !self.sleeping else { return }
                self.healthTask = nil
                if let data = data,
                   (response as? HTTPURLResponse)?.statusCode == 200,
                   let object = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any],
                   NavigationPolicy.matchesHealthIdentity(object, root: self.root) {
                    self.ready = true
                    self.attempts = 0
                    self.scheduleChecks(every: 20)
                    if self.needsReload {
                        self.needsReload = false
                        self.web.load(URLRequest(url: self.lastLocalURL))
                    }
                } else if let data = data,
                          let object = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any],
                          let identity = object["installation_id"] as? String,
                          identity != NavigationPolicy.installationID(root: self.root) {
                    self.cancelConnection()
                    self.statusPage("Another workspace is using this port", detail: "Port 8788 belongs to a different installation. No process was stopped. Close that installation yourself, then retry.")
                } else if self.attempts >= 40 {
                    self.cancelConnection()
                    self.statusPage("The local workspace is not ready", detail: "Use Help > Show Workspace and open start-u1-os.command for details, then use View > Reconnect. No other application was stopped.")
                } else {
                    self.ready = false
                    self.scheduleChecks(every: 0.75)
                    if response == nil { self.launchWorkspaceIfNeeded() }
                }
            }
        }
        healthTask?.resume()
    }

    func urlSession(_ session: URLSession, task: URLSessionTask, willPerformHTTPRedirection response: HTTPURLResponse, newRequest request: URLRequest, completionHandler: @escaping (URLRequest?) -> Void) {
        completionHandler(nil)
    }

    @objc func willSleep() { sleeping = true; cancelConnection() }
    @objc func didWake() { sleeping = false; startWorkspace() }
    func applicationDidBecomeActive(_ notification: Notification) {
        guard web != nil, !sleeping else { return }
        if timer == nil { startWorkspace() } else { connect() }
    }
    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        showWorkspace(); return true
    }
    func applicationWillTerminate(_ notification: Notification) {
        cancelConnection()
        healthSession.invalidateAndCancel()
        NSWorkspace.shared.notificationCenter.removeObserver(self)
        // The shared server may serve browser sessions; quitting does not kill it.
    }

    func statusPage(_ heading: String, detail: String) {
        ready = false
        needsReload = true
        web.loadHTMLString("""
        <!doctype html><html><meta name="viewport" content="width=device-width"><style>
        body{margin:0;min-height:100vh;display:grid;place-items:center;background:radial-gradient(ellipse at 50% 40%,#103a63,#020915 65%);color:#e0f2ff;font:17px -apple-system,sans-serif;text-align:center}main{max-width:560px;padding:42px;border:1px solid #286185;border-radius:30px;background:#061224bc;box-shadow:0 30px 100px #0007}.mark{font-size:94px;font-weight:750;letter-spacing:-8px;color:#99edff;text-shadow:0 0 36px #219ddd;animation:breathe 3s ease-in-out infinite}h1{font-size:25px;font-weight:500;letter-spacing:-.5px}p{color:#a7c6e4;line-height:1.7}small{letter-spacing:4px;color:#72d8ff;font-size:10px}a{display:inline-block;color:#caf2ff;padding:12px 20px;border:1px solid #397aa2;border-radius:12px;text-decoration:none;font-size:13px}.status{display:flex;gap:9px;justify-content:center;margin:24px 0;color:#8abdd7;font-size:10px;letter-spacing:1px}.status span{padding:8px;border-radius:7px;background:#12334b}@keyframes breathe{50%{text-shadow:0 0 58px #21c5ed;transform:translateY(-3px)}}@media(prefers-reduced-motion:reduce){*{animation:none!important}}
        </style><main><div class="mark" aria-label="U1 OS">U1</div><small>YOUR WORLD. AMPLIFIED.</small><h1>\(heading)</h1><p>\(detail)</p><div class="status"><span>LOCAL WORKSPACE</span><span>ACCOUNT ACCESS SEPARATE</span></div><a href="u1os://retry">Retry connection</a></main></html>
        """, baseURL: nil)
    }

    func createMenu() {
        let menu = NSMenu()
        let appItem = NSMenuItem()
        let appMenu = NSMenu()
        appMenu.addItem(withTitle: "About U1 OS", action: #selector(NSApplication.orderFrontStandardAboutPanel(_:)), keyEquivalent: "")
        if #available(macOS 13.0, *) {
            let login = appMenu.addItem(withTitle: "Start U1 OS at Login", action: #selector(toggleLogin(_:)), keyEquivalent: "")
            login.target = self
            login.state = SMAppService.mainApp.status == .enabled ? .on : .off
        }
        appMenu.addItem(.separator())
        appMenu.addItem(withTitle: "Hide U1 OS", action: #selector(NSApplication.hide(_:)), keyEquivalent: "h")
        appMenu.addItem(withTitle: "Quit U1 OS", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        appItem.submenu = appMenu
        menu.addItem(appItem)
        let edit = NSMenuItem(title: "Edit", action: nil, keyEquivalent: "")
        edit.submenu = NSMenu(title: "Edit")
        for (title, selector, key) in [("Undo","undo:","z"),("Cut","cut:","x"),("Copy","copy:","c"),("Paste","paste:","v"),("Select All","selectAll:","a")] {
            edit.submenu?.addItem(withTitle: title, action: Selector(selector), keyEquivalent: key)
        }
        menu.addItem(edit)
        let view = NSMenuItem(title: "View", action: nil, keyEquivalent: "")
        view.submenu = NSMenu(title: "View")
        let reload = view.submenu!.addItem(withTitle: "Reload", action: #selector(reloadWorkspace), keyEquivalent: "r")
        reload.target = self
        let reconnect = view.submenu!.addItem(withTitle: "Reconnect", action: #selector(reconnectWorkspace), keyEquivalent: "r")
        reconnect.keyEquivalentModifierMask = [.command, .shift]; reconnect.target = self
        let fullScreen = view.submenu!.addItem(withTitle: "Toggle Full Screen", action: #selector(NSWindow.toggleFullScreen(_:)), keyEquivalent: "f")
        fullScreen.keyEquivalentModifierMask = [.command, .control]
        menu.addItem(view)
        let windowItem = NSMenuItem(title: "Window", action: nil, keyEquivalent: "")
        let windows = NSMenu(title: "Window")
        windows.addItem(withTitle: "Minimise", action: #selector(NSWindow.performMiniaturize(_:)), keyEquivalent: "m")
        let show = windows.addItem(withTitle: "Show U1 OS", action: #selector(showWorkspace), keyEquivalent: "0")
        show.target = self
        windowItem.submenu = windows; menu.addItem(windowItem); NSApp.windowsMenu = windows
        let helpItem = NSMenuItem(title: "Help", action: nil, keyEquivalent: "")
        let help = NSMenu(title: "Help")
        let reveal = help.addItem(withTitle: "Show Workspace", action: #selector(revealWorkspace), keyEquivalent: "")
        reveal.target = self
        let release = help.addItem(withTitle: "Mac Release Guide", action: #selector(showReleaseGuide), keyEquivalent: "")
        release.target = self
        helpItem.submenu = help; menu.addItem(helpItem)
        NSApp.mainMenu = menu
    }

    @objc func reloadWorkspace() {
        needsReload = true
        startWorkspace()
    }

    @objc func reconnectWorkspace() { startWorkspace() }
    @objc func showWorkspace() {
        window.deminiaturize(nil)
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }
    @objc func revealWorkspace() {
        guard root.hasPrefix("/") else { return }
        NSWorkspace.shared.selectFile(nil, inFileViewerRootedAtPath: root)
    }
    @objc func showReleaseGuide() {
        let guide = URL(fileURLWithPath: root).appendingPathComponent("docs/MAC-RELEASE.md")
        if FileManager.default.fileExists(atPath: guide.path) { NSWorkspace.shared.activateFileViewerSelecting([guide]) }
    }

    @objc func toggleLogin(_ sender: NSMenuItem) {
        if #available(macOS 13.0, *) {
            do {
                if SMAppService.mainApp.status == .requiresApproval {
                    SMAppService.openSystemSettingsLoginItems(); return
                }
                if SMAppService.mainApp.status == .enabled { try SMAppService.mainApp.unregister() }
                else { try SMAppService.mainApp.register() }
                sender.state = SMAppService.mainApp.status == .enabled ? .on : .off
                if SMAppService.mainApp.status == .requiresApproval {
                    SMAppService.openSystemSettingsLoginItems()
                }
            } catch {
                let alert = NSAlert()
                alert.messageText = "Login startup was not changed"
                alert.informativeText = "macOS did not authorise this local app as a login item. You can add the Desktop app in System Settings > General > Login Items."
                alert.addButton(withTitle: "OK")
                alert.beginSheetModal(for: window)
            }
        }
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { false }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        if let url = webView.url, NavigationPolicy.isLocal(url) { lastLocalURL = url }
    }
    func recoverNavigation(_ error: Error) {
        if (error as NSError).code == NSURLErrorCancelled { return }
        needsReload = true; ready = false
        startWorkspace()
    }
    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) { recoverNavigation(error) }
    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) { recoverNavigation(error) }
    func webViewWebContentProcessDidTerminate(_ webView: WKWebView) {
        needsReload = true; ready = false; startWorkspace()
    }

    func webView(_ webView: WKWebView, decidePolicyFor action: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let url = action.request.url else { decisionHandler(.cancel); return }
        let trustedSource = action.sourceFrame.isMainFrame && action.sourceFrame.request.url.map { NavigationPolicy.isLocal($0) || $0.absoluteString == "about:blank" } == true
        if url.absoluteString == "u1os://retry", trustedSource, action.navigationType == .linkActivated {
            decisionHandler(.cancel)
            startWorkspace()
            return
        }
        let local = NavigationPolicy.isLocal(url)
        let localBlob = trustedSource && NavigationPolicy.isLocalBlob(url)
        if action.shouldPerformDownload {
            decisionHandler(trustedSource && (local || localBlob) ? .download : .cancel); return
        }
        if local || localBlob || url.absoluteString == "about:blank" {
            if action.targetFrame == nil { webView.load(action.request); decisionHandler(.cancel) }
            else { decisionHandler(.allow) }
            return
        }
        decisionHandler(.cancel)
        guard trustedSource, action.navigationType == .linkActivated,
              action.targetFrame?.isMainFrame != false,
              NavigationPolicy.canOpenExternally(url), !externalPromptOpen else { return }
        externalPromptOpen = true
        let alert = NSAlert()
        alert.messageText = "Open outside U1 OS?"
        alert.informativeText = "Open this link in your default application?\n\(url.absoluteString)"
        alert.addButton(withTitle: "Cancel"); alert.addButton(withTitle: "Open Link")
        alert.beginSheetModal(for: window) { [weak self] result in
            self?.externalPromptOpen = false
            if result == .alertSecondButtonReturn { NSWorkspace.shared.open(url) }
        }
    }

    func webView(_ webView: WKWebView, decidePolicyFor response: WKNavigationResponse, decisionHandler: @escaping (WKNavigationResponsePolicy) -> Void) {
        guard let url = response.response.url,
              NavigationPolicy.isLocal(url) || NavigationPolicy.isLocalBlob(url) || url.absoluteString == "about:blank" else {
            decisionHandler(.cancel); return
        }
        decisionHandler(response.canShowMIMEType ? .allow : .download)
    }
    func webView(_ webView: WKWebView, navigationAction: WKNavigationAction, didBecome download: WKDownload) { download.delegate = self }
    func webView(_ webView: WKWebView, navigationResponse: WKNavigationResponse, didBecome download: WKDownload) { download.delegate = self }
    func download(_ download: WKDownload, decideDestinationUsing response: URLResponse, suggestedFilename: String, completionHandler: @escaping (URL?) -> Void) {
        let panel = NSSavePanel()
        panel.nameFieldStringValue = (suggestedFilename as NSString).lastPathComponent
        panel.beginSheetModal(for: window) { result in completionHandler(result == .OK ? panel.url : nil) }
    }
    func webView(_ webView: WKWebView, runOpenPanelWith parameters: WKOpenPanelParameters, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping ([URL]?) -> Void) {
        let panel = NSOpenPanel()
        panel.allowsMultipleSelection = parameters.allowsMultipleSelection
        panel.canChooseDirectories = parameters.allowsDirectories
        panel.canChooseFiles = true
        panel.beginSheetModal(for: window) { result in completionHandler(result == .OK ? panel.urls : nil) }
    }
    func webView(_ webView: WKWebView, runJavaScriptAlertPanelWithMessage message: String, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping () -> Void) {
        let alert = NSAlert(); alert.messageText = "U1 OS"; alert.informativeText = message; alert.addButton(withTitle: "OK")
        alert.beginSheetModal(for: window) { _ in completionHandler() }
    }
    func webView(_ webView: WKWebView, runJavaScriptConfirmPanelWithMessage message: String, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping (Bool) -> Void) {
        let alert = NSAlert(); alert.messageText = "U1 OS"; alert.informativeText = message
        alert.addButton(withTitle: "Continue"); alert.addButton(withTitle: "Cancel")
        alert.beginSheetModal(for: window) { result in completionHandler(result == .alertFirstButtonReturn) }
    }
}

@main
enum U1Desktop {
    static func main() {
        let app = NSApplication.shared
        let delegate = U1Application()
        app.delegate = delegate
        app.setActivationPolicy(.regular)
        withExtendedLifetime(delegate) { app.run() }
    }
}
