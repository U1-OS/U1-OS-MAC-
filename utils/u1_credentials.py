"""Image-only native Keychain helper. Secrets travel through stdin/stdout pipes only."""
import json
import os
from pathlib import Path
import stat
import subprocess
import threading

_build_lock = threading.Lock()
SWIFT = r'''
import Foundation
import Security

func fail() -> Never {
    FileHandle.standardOutput.write(Data("{\"success\":false}".utf8))
    exit(1)
}
guard CommandLine.arguments.count == 2 else { fail() }
let operation = CommandLine.arguments[1]
let query: [String: Any] = [kSecClass as String: kSecClassGenericPassword,
    kSecAttrService as String: "local.u1os.openai.images",
    kSecAttrAccount as String: "openai-images-api"]
switch operation {
case "get":
    var lookup = query
    lookup[kSecReturnData as String] = true
    lookup[kSecMatchLimit as String] = kSecMatchLimitOne
    var result: CFTypeRef?
    guard SecItemCopyMatching(lookup as CFDictionary, &result) == errSecSuccess,
          let data = result as? Data, data.count <= 8192 else { fail() }
    FileHandle.standardOutput.write(data)
case "set":
    let data = FileHandle.standardInput.readData(ofLength: 8193)
    guard data.count <= 8192,
          let object = try? JSONSerialization.jsonObject(with: data) as? [String: String],
          let key = object["api_key"], key.utf8.count <= 4096,
          key.hasPrefix("sk-") else { fail() }
    let update = [kSecValueData as String: data]
    var result = SecItemUpdate(query as CFDictionary, update as CFDictionary)
    if result == errSecItemNotFound {
        var item = query
        item[kSecValueData as String] = data
        item[kSecAttrLabel as String] = "U1 OS OpenAI Images API"
        result = SecItemAdd(item as CFDictionary, nil)
    }
    guard result == errSecSuccess else { fail() }
    FileHandle.standardOutput.write(Data("{\"success\":true}".utf8))
case "delete":
    let result = SecItemDelete(query as CFDictionary)
    guard result == errSecSuccess || result == errSecItemNotFound else { fail() }
    FileHandle.standardOutput.write(Data("{\"success\":true}".utf8))
default: fail()
}
'''


def helper_path(root):
    return Path(root) / 'credentials' / 'image-keychain'


def _trusted_helper(path):
    try:
        info = path.lstat()
        return (stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid()
                and not info.st_mode & 0o022 and info.st_nlink == 1
                and os.access(path, os.X_OK) and not path.parent.is_symlink())
    except OSError:
        return False


def ready(root):
    return _trusted_helper(helper_path(root))


def ensure_helper(root):
    """Compile only on explicit credential setup. Does not access Keychain."""
    from utils.u1_assistant import _private_dir, _atomic_write
    with _build_lock:
        helper = helper_path(root)
        if _trusted_helper(helper):
            return helper
        _private_dir(helper.parent)
        cache = helper.parent / 'compiler-cache'
        _private_dir(cache)
        source = helper.parent / 'ImageKeychain.swift'
        _atomic_write(source, SWIFT.encode('utf-8'))
        target = helper.parent / 'image-keychain-building'
        environment = dict(PATH='/usr/bin:/bin:/usr/sbin:/sbin', HOME=str(Path.home()),
                           TMPDIR=str(cache), CLANG_MODULE_CACHE_PATH=str(cache), LANG='en_US.UTF-8')
        try:
            result = subprocess.run(['/usr/bin/xcrun', 'swiftc', str(source), '-o', str(target),
                                     '-framework', 'Security'], shell=False, env=environment,
                                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, timeout=90, check=False)
            if result.returncode or not target.is_file() or target.is_symlink():
                raise ValueError('Native Keychain helper setup failed. Install Apple command line tools and retry.')
            target.chmod(0o700)
            os.replace(target, helper)
            return helper
        except (OSError, subprocess.TimeoutExpired):
            raise ValueError('Native Keychain helper setup did not complete.') from None
        finally:
            target.unlink(missing_ok=True)


def operation(helper, action, value=None):
    helper = Path(helper)
    if action not in {'get', 'set', 'delete'} or not _trusted_helper(helper):
        raise ValueError('Native image Keychain helper is unavailable.')
    content = json.dumps(value, separators=(',', ':')).encode() if value is not None else b''
    if len(content) > 8192:
        raise ValueError('Credential input exceeds the allowed size.')
    try:
        result = subprocess.run([str(helper), action], input=content, shell=False,
                                env=dict(PATH='/usr/bin:/bin', HOME=str(Path.home()), LANG='en_US.UTF-8'),
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=35, check=False)
        if result.returncode or len(result.stdout) > 8192:
            raise ValueError('Keychain unavailable or access denied. No plaintext fallback was used.')
        data = json.loads(result.stdout)
        if not isinstance(data, dict):
            raise ValueError('Invalid Keychain result.')
        return data
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError, UnicodeError):
        raise ValueError('The native Keychain operation did not complete.') from None
