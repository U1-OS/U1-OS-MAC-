import Foundation

@main
enum PolicyChecks {
    static func main() {
        var count = 0
        func check(_ result: Bool, _ name: String) {
            count += 1
            guard result else { fatalError("Navigation policy failed: \(name)") }
        }
        for raw in ["http://127.0.0.1:8788/", "http://127.0.0.1:8788/api/integrations"] {
            check(NavigationPolicy.isLocal(URL(string: raw)!), "local origin")
        }
        for raw in ["https://127.0.0.1:8788", "http://localhost:8788", "http://127.0.0.1:9999", "http://127.0.0.1:8788.evil.example", "http://user@127.0.0.1:8788", "file:///tmp/export.html", "data:text/html,test"] {
            check(URL(string: raw).map { !NavigationPolicy.isLocal($0) } ?? true, "reject foreign origin")
        }
        check(NavigationPolicy.isLocalBlob(URL(string: "blob:http://127.0.0.1:8788/123")!), "local export")
        check(!NavigationPolicy.isLocalBlob(URL(string: "blob:https://example.com/123")!), "foreign export")
        for raw in ["https://example.com/path", "http://example.com", "mailto:person@example.com"] {
            check(NavigationPolicy.canOpenExternally(URL(string: raw)!), "ordinary external link")
        }
        for raw in ["file:///tmp/app", "javascript:alert(1)", "tel:123", "https://user:secret@example.com", "https://example.com/%0a", "u1os://retry"] {
            check(!NavigationPolicy.canOpenExternally(URL(string: raw)!), "unsafe opener")
        }
        check(NavigationPolicy.matchesWorkspace("/tmp/u1/../u1", root: "/tmp/u1"), "canonical owner")
        check(!NavigationPolicy.matchesWorkspace("/tmp/other", root: "/tmp/u1"), "foreign owner")
        check(!NavigationPolicy.matchesWorkspace(nil, root: "/tmp/u1"), "missing owner")
        print("PASS: \(count) native navigation/ownership checks")
    }
}
