import Foundation

enum NavigationPolicy {
    static let base = URL(string: "http://127.0.0.1:8788/")!

    static func isLocal(_ url: URL) -> Bool {
        url.scheme == "http" && url.host == "127.0.0.1" && url.port == 8788
            && url.user == nil && url.password == nil
    }

    static func isLocalBlob(_ url: URL) -> Bool {
        guard url.scheme == "blob", let origin = URL(string: String(url.absoluteString.dropFirst(5))) else { return false }
        return isLocal(origin)
    }

    static func canOpenExternally(_ url: URL) -> Bool {
        guard url.user == nil, url.password == nil,
              let decoded = url.absoluteString.removingPercentEncoding,
              decoded.rangeOfCharacter(from: .controlCharacters) == nil else { return false }
        if url.scheme == "mailto" { return !url.path.isEmpty }
        return ["http", "https"].contains(url.scheme ?? "") && !(url.host ?? "").isEmpty
    }

    static func matchesWorkspace(_ value: Any?, root: String) -> Bool {
        guard let path = value as? String, path.hasPrefix("/"), !root.isEmpty else { return false }
        return URL(fileURLWithPath: path).standardizedFileURL.resolvingSymlinksInPath()
            == URL(fileURLWithPath: root).standardizedFileURL.resolvingSymlinksInPath()
    }
}
