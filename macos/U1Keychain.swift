import Foundation
import Security

// Credential data arrives on stdin, never in command-line arguments or logs.
func fail() -> Never {
    FileHandle.standardOutput.write(Data("{\"success\":false,\"error\":\"Keychain unavailable or access denied.\"}".utf8))
    exit(1)
}
guard CommandLine.arguments.count == 3 else { fail() }
let operation = CommandLine.arguments[1]
let account = CommandLine.arguments[2]
guard account.range(of: "^[a-f0-9]{32}$", options: .regularExpression) != nil else { fail() }
let query: [String: Any] = [kSecClass as String: kSecClassGenericPassword,
                          kSecAttrService as String: "local.u1os.google.readonly",
                          kSecAttrAccount as String: account]
switch operation {
case "get":
    var readQuery = query
    readQuery[kSecReturnData as String] = true
    readQuery[kSecMatchLimit as String] = kSecMatchLimitOne
    var result: CFTypeRef?
    guard SecItemCopyMatching(readQuery as CFDictionary, &result) == errSecSuccess,
          let data = result as? Data else { fail() }
    FileHandle.standardOutput.write(data)
case "set":
    let data = FileHandle.standardInput.readDataToEndOfFile()
    guard data.count <= 65536, (try? JSONSerialization.jsonObject(with: data)) != nil else { fail() }
    let update = [kSecValueData as String: data]
    var status = SecItemUpdate(query as CFDictionary, update as CFDictionary)
    if status == errSecItemNotFound {
        var item = query
        item[kSecValueData as String] = data
        item[kSecAttrLabel as String] = "U1 OS Google read-only connection"
        status = SecItemAdd(item as CFDictionary, nil)
    }
    guard status == errSecSuccess else { fail() }
    FileHandle.standardOutput.write(Data("{\"success\":true}".utf8))
case "delete":
    let status = SecItemDelete(query as CFDictionary)
    guard status == errSecSuccess || status == errSecItemNotFound else { fail() }
    FileHandle.standardOutput.write(Data("{\"success\":true}".utf8))
default: fail()
}
