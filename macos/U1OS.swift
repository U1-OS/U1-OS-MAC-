import AppKit
import WebKit
import ServiceManagement

final class U1Application: NSObject, NSApplicationDelegate, WKNavigationDelegate, WKUIDelegate, WKDownloadDelegate {
    var window: NSWindow!
    var web: WKWebView!
    var launcher: Process?
    var timer: Timer?
    var attempts = 0
    var polling = false
    let base = URL(string: "http://127.0.0.1:8788")!
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
        window.backgroundColor = NSColor(calibratedRed: 0.025, green: 0.055, blue: 0.10, alpha: 1)
        window.contentView = web
        window.center()
        window.makeKeyAndOrderFront(nil)
        createMenu()
        NSApp.activate(ignoringOtherApps: true)
        startWorkspace()
    }

    func startWorkspace() {
        timer?.invalidate()
        attempts = 0
        polling = false
        statusPage("Starting your workspace", detail: "Connecting to your private local U1 OS installation.")
        guard !root.isEmpty else { statusPage("Installation path is missing", detail: "Rebuild the desktop application from your U1 OS workspace."); return }
        if launcher?.isRunning == true {
            timer = Timer.scheduledTimer(withTimeInterval: 0.75, repeats: true) { [weak self] _ in self?.connect() }
            connect()
            return
        }
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/bin/zsh")
        process.arguments = [root + "/start-u1-os.command", "--no-browser"]
        process.currentDirectoryURL = URL(fileURLWithPath: root)
        process.standardOutput = FileHandle.nullDevice
        process.standardError = FileHandle.nullDevice
        launcher = process
        do { try process.run() } catch { statusPage("The workspace could not start", detail: "Open start-u1-os.command in your installation for details."); return }
        timer = Timer.scheduledTimer(withTimeInterval: 0.75, repeats: true) { [weak self] _ in self?.connect() }
        connect()
    }

    func connect() {
        guard !polling else { return }
        polling = true
        attempts += 1
        var request = URLRequest(url: base.appendingPathComponent("api/integrations"))
        request.timeoutInterval = 2
        request.cachePolicy = .reloadIgnoringLocalCacheData
        URLSession.shared.dataTask(with: request) { [weak self] data, response, _ in
            DispatchQueue.main.async {
                guard let self = self else { return }
                self.polling = false
                if let data = data,
                   (response as? HTTPURLResponse)?.statusCode == 200,
                   let object = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any],
                   object["installation_root"] as? String == self.root {
                    self.timer?.invalidate()
                    self.web.load(URLRequest(url: URL(string: "http://127.0.0.1:8788/#home")!))
                } else if self.attempts >= 40 {
                    self.timer?.invalidate()
                    self.statusPage("The local workspace is not ready", detail: "Open start-u1-os.command for details, then use View > Reload. No other application was stopped.")
                }
            }
        }.resume()
    }

    func statusPage(_ heading: String, detail: String) {
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
        view.submenu?.addItem(withTitle: "Enter Full Screen", action: #selector(NSWindow.toggleFullScreen(_:)), keyEquivalent: "f")
        menu.addItem(view)
        NSApp.mainMenu = menu
    }

    @objc func reloadWorkspace() {
        if web.url?.host == "127.0.0.1" { web.reload() }
        else { startWorkspace() }
    }

    @objc func toggleLogin(_ sender: NSMenuItem) {
        if #available(macOS 13.0, *) {
            do {
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

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }

    func webView(_ webView: WKWebView, decidePolicyFor action: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let url = action.request.url else { decisionHandler(.cancel); return }
        if url.scheme == "u1os", url.host == "retry" {
            decisionHandler(.cancel)
            startWorkspace()
            return
        }
        if action.shouldPerformDownload { decisionHandler(.download); return }
        if action.targetFrame?.isMainFrame == true || action.targetFrame == nil {
            let local = url.scheme == "http" && url.host == "127.0.0.1" && url.port == 8788
            if !local && ["http", "https", "mailto"].contains(url.scheme ?? "") {
                NSWorkspace.shared.open(url)
                decisionHandler(.cancel)
                return
            }
            if !local && !["about", "blob", "data"].contains(url.scheme ?? "") { decisionHandler(.cancel); return }
            if action.targetFrame == nil { webView.load(action.request); decisionHandler(.cancel); return }
        }
        decisionHandler(.allow)
    }

    func webView(_ webView: WKWebView, decidePolicyFor response: WKNavigationResponse, decisionHandler: @escaping (WKNavigationResponsePolicy) -> Void) {
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

let app = NSApplication.shared
let delegate = U1Application()
app.delegate = delegate
app.setActivationPolicy(.regular)
app.run()
