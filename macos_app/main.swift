import Cocoa
import WebKit

class AppDelegate: NSObject, NSApplicationDelegate {
    var statusItem: NSStatusItem!
    var window: NSWindow!
    var webView: WKWebView!

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

        // 5. Load Command Center URL
        if let url = URL(string: "http://127.0.0.1:8787") {
            let request = URLRequest(url: url)
            webView.load(request)
        }

        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
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
