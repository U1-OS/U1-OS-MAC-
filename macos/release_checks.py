"""Explicit personal U1 release checks. Never discover the inherited test suite."""
import argparse
import ast
import fcntl
from datetime import datetime, timezone
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import signal
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.parse

ROOT = Path(__file__).resolve().parents[1]
TEST_FILES = tuple("tests/test_" + name + ".py" for name in (
    "u1_business", "u1_reliability", "u1_autopilot", "u1_reminders", "u1_launcher", "u1_agent_centre",
    "updater", "integrations_hub", "u1_studio_pro", "u1_personal_core", "u1_assistant", "u1_safety",
    "u1_private_backup", "u1_release_guard", "u1_native_routes", "u1_media_research", "u1_image_provider", "u1_macos_release",
    "u1_operational_safety", "u1_usage_windows", "u1_osint_tools", "u1_media_download",
    "u1_discovery", "u1_spotify", "u1_connection_preflight", "u1_server_boundaries", "u1_provider_boundaries",
    "u1_assistant_retention", "u1_information_truth", "u1_data_boundaries"))
TEST_FIXTURES = {"tests/test_u1_image_provider.py": ("tests/test_u1_assistant.py",)}
JS_TESTS = {
    "tests/test_u1_connections.cjs": ("static/js/u1-connection-policy.js", "static/js/u1-connections-workspace.js", "static/css/u1-connections-workspace.css"),
    "tests/test_u1_media.mjs": ("static/js/u1-media-core.mjs",),
    "tests/test_u1_shell_navigation.cjs": ("static/js/u1-core-workspaces.js",),
    "tests/test_u1_build_status.cjs": ("static/js/u1-build-status.js", "docs/BUILD-STATUS.md"),
    "tests/test_u1_daily_flow.cjs": ("static/js/u1-daily-flow.js", "static/css/u1-daily-flow.css"),
    "tests/test_u1_usage_selection.cjs": ("static/js/u1-platform-core.js",),
    "tests/test_u1_operational_polish.cjs": ("static/js/u1-operational-polish.js",),
    "tests/test_u1_rounded_system.cjs": ("static/js/u1-rounded-system.js", "static/js/u1-cinematic.js", "static/js/u1-safety.js"),
    "tests/test_u1_assistant_workspace.js": ("static/js/u1-assistant-workspace.js",),
    "tests/test_u1_create_earn.cjs": ("static/js/u1-create-earn-workspaces.js",),
    "tests/test_u1_studio_drafts.cjs": ("static/js/u1-studio-pro.js",),
    "tests/test_u1_rounded_contrast.cjs": ("static/css/u1-rounded-system.css",),
    "tests/test_u1_discovery_truth.cjs": ("static/js/u1-discovery-workspace.js", "static/js/u1-workspaces.js"),
    "tests/test_u1_navigation_adversarial.cjs": (
        "static/js/u1-connection-policy.js", "static/js/u1-connections-workspace.js",
        "static/js/u1-core-workspaces.js", "static/js/u1-data.js", "static/js/u1-media-research.js",
        "static/js/u1-platform-core.js", "static/js/u1-platform.js", "static/js/u1-safety.js", "static/js/u1os.js"),
    "tests/test_u1_rounded_navigation.cjs": (
        "static/u1os.html", "static/js/u1-native-operations.js", "static/js/u1-platform-core.js",
        "static/js/u1-platform.js", "static/js/u1-rounded-system.js"),
    "tests/test_u1_platform.cjs": ("static/js/u1-platform-core.js",),
    "tests/test_u1_operational_navigation.cjs": (
        "static/u1os.html", "static/js/u1-native-operations.js", "static/js/u1os.js",
        "static/js/u1-platform.js", "utils/u1_native_routes.py", "server.py"),
}
PYTHON_NODE_FIXTURES = {
    "tests/test_u1_studio_pro.py": "static/js/u1-studio-pro.js",
    "tests/test_u1_discovery.py": "static/js/u1-discovery-workspace.js",
    "tests/test_u1_osint_tools.py": "static/js/u1-media-research.js",
}
JS_CONTRACT_MARKERS = {
    "tests/test_u1_shell_navigation.cjs": ("PASS 6 native registration and direct-entry contracts", 6),
    "tests/test_u1_assistant_workspace.js": ("\n".join((
        "PASS testOutOfOrder", "PASS testSendBlockedDuringReviewLoad", "PASS testCurrentReviewIsSent",
        "PASS testSelectionChangeDuringCsrfPreventsPost", "PASS testHistoryChangeInvalidatesConsent",
        "PASS testIdentityMismatchIsRejected", "PASS testLifecyclePreservesDraftAndOnlyReads",
        "7 assistant consent/lifecycle tests passed; all I/O mocked.")), 7),
}
OPT_IN_TESTS = {
    "tests/test_u1_media_research.py": {
        "SyntheticFFmpegTests.test_generated_owned_video_exports_real_mp4_and_wav",
        "SyntheticFFmpegTests.test_real_empty_outputs_are_rejected_even_when_ffmpeg_returns_zero",
        "SyntheticFFmpegTests.test_real_short_audio_cannot_pass_a_longer_export_contract"},
}
JS_SYNTAX_FILES = ("static/js/u1-image-provider.js", "static/js/u1-spotify-widget.js",
                   "static/js/u1-activation-workspace.js", "static/js/u1-discovery-workspace.js",
                   "static/js/u1-osint-tools.js", "static/js/u1-media-download.js", "static/js/u1-feedback.js")
PYTHON_FILES = ("macos/release_checks.py", "macos/release_support.py",
                "utils/u1_studio_pro.py", "utils/u1_personal_core.py", "utils/u1_assistant.py",
                "utils/u1_credentials.py", "utils/u1_image_provider.py", "utils/u1_safety.py",
                "utils/u1_usage_windows.py", "utils/u1_discovery.py", "utils/u1_osint_tools.py",
                "utils/u1_media_download.py", "utils/u1_spotify.py", "utils/u1_connection_preflight.py",
                "utils/u1_google.py", "utils/workspace_hub.py", "server.py", "launch_u1.py",
                "services/crypto.py", "services/intelligence.py", "utils/briefing.py", "utils/news_markets.py",
                "utils/prism_workspace.py", "utils/u1_recovery.py")
SHELL_FILES = ("scripts/check-personal-release.sh", "macos/build-desktop.sh", "macos/install-u1.sh", "macos/bootstrap-personal.sh")
WORKFLOW = ".github/workflows/personal-os-quality.yml"


def select_tests(root):
    present, missing = [], []
    for name in TEST_FILES:
        path = Path(root) / name
        if path.is_symlink():
            raise ValueError("Release tests cannot be symlinks: " + name)
        (present if path.is_file() else missing).append(name)
    return present, missing


def result_status(results, missing, syntax_failed=False):
    if syntax_failed or any(item["status"] == "FAIL" for item in results):
        return "FAIL"
    if missing or any(item["status"] == "PARTIAL" for item in results):
        return "PARTIAL"
    return "PASS" if results else "FAIL"


def unit_suite(suite, name):
    selected, excluded = unittest.TestSuite(), []
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            children, omitted = unit_suite(item, name)
            selected.addTests(children)
            excluded.extend(omitted)
        else:
            identifier = item.__class__.__name__ + "." + item._testMethodName
            if identifier in OPT_IN_TESTS.get(name, set()):
                excluded.append(identifier)
            else:
                selected.addTest(item)
    return selected, excluded


def js_command(name, root, node):
    if name not in JS_TESTS or not node:
        raise PermissionError("An available Node executable and an explicit JavaScript test are required")
    paths = [Path(root).resolve() / value for value in (name, *JS_TESTS[name])]
    if any(path.is_symlink() or not path.is_file() for path in paths):
        raise ValueError("JavaScript tests require ordinary existing source files")
    command = [node, "--permission", "--test-reporter=tap"]
    command.extend("--allow-fs-read=" + str(path) for path in paths)
    return command + [str(paths[0])]


def javascript_result(name, returncode, stdout):
    if name in JS_CONTRACT_MARKERS:
        marker, count = JS_CONTRACT_MARKERS[name]
        passed = returncode == 0 and stdout.strip() == marker
        return dict(file=name, status="PASS" if passed else "FAIL", tests=count if passed else 0,
                    failures=0, errors=0 if passed else 1, skipped=0)
    counts = {key: int(value) for key, value in re.findall(r"^# (tests|pass|fail|cancelled|skipped|todo) (\d+)\s*$", stdout, re.MULTILINE)}
    complete = all(key in counts for key in ("tests", "pass", "fail", "cancelled", "skipped", "todo"))
    passed = complete and returncode == 0 and counts["tests"] > 0 and counts["pass"] == counts["tests"]
    return dict(file=name, status="PASS" if passed else "FAIL", tests=counts.get("tests", 0),
                failures=counts.get("fail", 0), errors=0 if passed else 1,
                skipped=counts.get("skipped", 0) + counts.get("todo", 0))


def node_command(command, root, node, fixture="tests/test_u1_studio_pro.py"):
    relative = PYTHON_NODE_FIXTURES.get(fixture)
    if (not relative or not node or not isinstance(command, (list, tuple))
            or len(command) not in (3, 4) or command[0] not in ("node", node)
            or command[1] != "-e" or not isinstance(command[2], str)):
        raise PermissionError("Only an explicitly named JavaScript helper may run")
    script = Path(root) / relative
    if script.is_symlink():
        raise PermissionError("JavaScript helper sources cannot be symlinks")
    harness = command[2]
    if fixture == "tests/test_u1_discovery.py":
        reference = "require('./static/js/u1-discovery-workspace.js')"
        if len(command) != 3 or harness.count(reference) != 1:
            raise PermissionError("Discovery requires its exact reviewed helper reference")
        harness = harness.replace(reference, "require(" + json.dumps(str(script)) + ")")
    elif len(command) != 4 or str(command[3]) != str(script):
        raise PermissionError("JavaScript helper source must match its named Python fixture")
    prelude = "if(Number(process.versions.node.split('.')[0])<26)throw Error('Release harness requires Node 26 or later');\n"
    return [node, "--permission", "--allow-fs-read=" + str(script), "-e", prelude + harness, str(script)]


def node_launch_options(options, temporary):
    """Preserve the acceptance runner's stdio pipes without granting new resources."""
    if (options.get("shell") or options.get("executable") or options.get("preexec_fn")
            or options.get("pass_fds") or options.get("process_group") is not None):
        raise PermissionError("Shells, alternate executables and extra inherited descriptors are forbidden")
    confined = dict(options)
    confined.update(cwd=str(temporary), env=dict(os.environ), shell=False,
                    close_fds=True, start_new_session=False)
    return confined


def scoped_open(original_open, context):
    """Carry openat's descriptor into its audit event without changing the call.

    CPython's open event supplies path/mode/flags, but omits dir_fd. Preserve
    per-thread context only during the original operation; never replace its
    descriptor-relative, O_NOFOLLOW-protected open with an absolute-path open.
    """
    def opened(path, flags, mode=0o777, *, dir_fd=None):
        previous = getattr(context, "dir_fd", None)
        context.dir_fd = dir_fd
        try:
            return original_open(path, flags, mode, dir_fd=dir_fd)
        finally:
            context.dir_fd = previous
    return opened


def guard_event(event, args, root, temporary, allowed_processes=(), *, open_dir_fd=None):
    """Regression guard for trusted tests, not an OS sandbox for hostile Python."""
    root, temporary = Path(root), Path(temporary)

    def checked_path(raw, write=False, dir_fd=None):
        if isinstance(raw, int):
            return
        path = Path(os.fsdecode(raw))
        if not path.is_absolute() and isinstance(dir_fd, int) and dir_fd >= 0:
            if sys.platform == "darwin":
                directory = os.fsdecode(fcntl.fcntl(dir_fd, 50, b"\0" * 1024).split(b"\0", 1)[0])
            else:
                directory = os.readlink("/proc/self/fd/" + str(dir_fd))
            path = Path(directory) / path
        path = path.resolve()
        if path == temporary or temporary in path.parents:
            return
        if write:
            raise PermissionError("Release tests may write only to their temporary directory")
        # The existing venv lives in .runtime: permit its libraries, not its helpers/data.
        libraries = [Path(sys.base_prefix).resolve() / "lib", Path(sys.prefix).resolve() / "lib",
                     Path("/usr/lib"), Path("/usr/share/zoneinfo"), Path("/System/Library")]
        if path == Path(os.devnull) or any(path == base.resolve() or base.resolve() in path.parents for base in libraries):
            return
        if path == root or root in path.parents:
            relative = path.relative_to(root)
            if any(part in {"data", ".runtime", ".git", "backups", "dist", "node_modules"} or part.startswith(".env") for part in relative.parts):
                raise PermissionError("Release tests cannot read workspace data or credentials")
            if path.suffix.lower() in {".db", ".sqlite", ".sqlite3", ".pem", ".key", ".log"}:
                raise PermissionError("Release tests cannot read private runtime files")
            return
        raise PermissionError("Release tests cannot read outside source, libraries and fixtures")

    if event in {"subprocess.Popen", "os.system", "os.posix_spawn", "os.exec", "os.fork", "pty.spawn"}:
        if event == "subprocess.Popen" and len(args) > 1 and tuple(args[1]) in allowed_processes:
            return
        raise PermissionError("Release tests must mock subprocess and Keychain access")
    if event in {"socket.connect", "socket.connect_ex", "socket.bind", "socket.getaddrinfo", "socket.sendto"}:
        raise PermissionError("Release tests must mock network access")
    if event == "open":
        mode, flags = args[1], args[2]
        write = bool(isinstance(mode, str) and any(letter in mode for letter in "wax+"))
        write = write or bool(isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
        checked_path(args[0], write, open_dir_fd)
    elif event == "sqlite3.connect" and str(args[0]) != ":memory:":
        raw = os.fsdecode(args[0])
        if raw.startswith("file:"):
            uri = urllib.parse.urlsplit(raw)
            if uri.netloc not in {"", "localhost"}:
                raise PermissionError("Remote SQLite URI is forbidden")
            raw = urllib.parse.unquote(uri.path)
        checked_path(raw, True)
    elif event in {"os.remove", "os.rmdir"}:
        checked_path(args[0], True, args[1] if len(args) > 1 else None)
    elif event in {"os.mkdir", "os.chmod", "os.utime"}:
        checked_path(args[0], True, args[-1] if len(args) >= 3 else None)
    elif event == "os.truncate":
        checked_path(args[0], True)
    elif event in {"os.rename", "os.link"}:
        checked_path(args[0], True, args[2] if len(args) > 2 else None)
        checked_path(args[1], True, args[3] if len(args) > 3 else None)
    elif event == "os.symlink":
        checked_path(args[0], True)
        checked_path(args[1], True, args[2] if len(args) > 2 else None)
    elif event in {"os.listdir", "os.scandir"}:
        checked_path(args[0] if args and args[0] is not None else os.getcwd())


def worker(name, output, temporary):
    if name not in TEST_FILES:
        raise ValueError("Only explicitly selected U1 tests may execute")
    temporary = Path(temporary).resolve()
    node = os.environ.get("U1_RELEASE_NODE")
    os.environ.clear()
    os.environ.update(HOME=str(temporary / "home"), TMPDIR=str(temporary),
                      PRISM_DATA_DIR=str(temporary / "prism"), XDG_DATA_HOME=str(temporary / "data"),
                      XDG_CACHE_HOME=str(temporary / "cache"), PATH="/usr/bin:/bin",
                      PYTHONDONTWRITEBYTECODE="1", U1_RELEASE_ISOLATED="1")
    (temporary / "home").mkdir(exist_ok=True)
    tempfile.tempdir = str(temporary)
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(ROOT))
    allowed_processes = set()
    open_context = threading.local()
    os.open = scoped_open(os.open, open_context)
    if name in PYTHON_NODE_FIXTURES:
        original_popen = subprocess.Popen
        original_which = shutil.which
        shutil.which = lambda command, *args, **kwargs: node if command == "node" else original_which(command, *args, **kwargs)
        def isolated_node(command, *arguments, **options):
            command = node_command(command, ROOT, node, name)
            options = node_launch_options(options, temporary)
            allowed_processes.add(tuple(command))
            return original_popen(command, *arguments, **options)
        subprocess.Popen = isolated_node
    sys.addaudithook(lambda event, args: guard_event(event, args, ROOT, temporary, allowed_processes,
                                                  open_dir_fd=getattr(open_context, "dir_fd", None)))
    stream = io.StringIO()
    try:
        # The image suite reuses assistant fixture classes without rerunning them.
        # Load this one named dependency explicitly; never add the whole tests directory.
        for fixture in TEST_FIXTURES.get(name, ()):
            fixture_path = ROOT / fixture
            if fixture_path.is_symlink():
                raise ValueError("Release fixture modules cannot be symlinks")
            fixture_name = fixture_path.stem
            fixture_spec = importlib.util.spec_from_file_location(fixture_name, fixture_path)
            fixture_module = importlib.util.module_from_spec(fixture_spec)
            sys.modules[fixture_name] = fixture_module
            fixture_spec.loader.exec_module(fixture_module)
        spec = importlib.util.spec_from_file_location("u1_release_selected_test", ROOT / name)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        suite, excluded = unit_suite(unittest.defaultTestLoader.loadTestsFromModule(module), name)
        result = unittest.TextTestRunner(stream=stream, verbosity=1).run(suite)
        status = "FAIL" if not result.wasSuccessful() or not result.testsRun else "PARTIAL" if result.skipped else "PASS"
        record = dict(file=name, status=status, tests=result.testsRun,
                      failures=len(result.failures), errors=len(result.errors), skipped=len(result.skipped),
                      opt_in_not_run=excluded)
        if status != "PASS":
            print(stream.getvalue(), file=sys.stderr)
    except Exception as error:
        record = dict(file=name, status="FAIL", tests=0, failures=0, errors=1, skipped=0,
                      reason=type(error).__name__)
        print(name + ": import/fixture failure: " + type(error).__name__ + ": " + str(error), file=sys.stderr)
    Path(output).write_text(json.dumps(record), encoding="utf-8")
    return 0 if record["status"] == "PASS" else 1


def navigation_preload(folder, env):
    """Execute Mill's exact embedded Python once, without granting Node children.

    The unchanged Node assertion receives that actual completed process result.
    A preload checks its exact invocation and requires exactly one consumption.
    """
    source = (folder / "tests/test_u1_operational_navigation.cjs").read_text()
    matches = re.findall(r"const code = String\.raw`([^`]*)`;", source)
    if len(matches) != 1:
        raise ValueError("Expected exactly one reviewed operational Python fixture")
    code = matches[0]
    bootstrap = (
        "import importlib.util, pathlib, sys\n"
        "spec=importlib.util.spec_from_file_location('release_guard', " + repr(str(Path(__file__).resolve())) + ")\n"
        "guard=importlib.util.module_from_spec(spec); spec.loader.exec_module(guard)\n"
        "root=pathlib.Path(" + repr(str(folder)) + ")\n"
        "sys.path.insert(0, str(root))\n"
        "sys.addaudithook(lambda event,args: guard.guard_event(event,args,root,root))\n"
        "exec(compile(" + repr(code) + ", '<operational-navigation-fixture>', 'exec'))\n"
    )
    result = subprocess.run([sys.executable, "-I", "-B", "-c", bootstrap],
                            cwd=str(folder), env=env, capture_output=True, text=True, timeout=10)
    record = dict(status=result.returncode, stdout=result.stdout, stderr=result.stderr)
    if result.returncode:
        raise ValueError("Operational navigation Python fixture failed: " + result.stderr[-2000:])
    shim = folder / "operational-python-result.cjs"
    shim.write_text(
        "'use strict';\nconst cp=require('node:child_process');let calls=0;\n"
        "cp.spawnSync=(command,args,options)=>{if(command!=='python3'||"
        "JSON.stringify(args)!==JSON.stringify(['-c'," + json.dumps(code) + "])||"
        "options.cwd!==" + json.dumps(str(folder)) + ")throw Error('Unreviewed child invocation');"
        "calls++;return " + json.dumps(record) + ";};\n"
        "process.on('exit',()=>{if(calls!==1)process.exitCode=1;});\n", encoding="utf-8")
    return shim


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-all", action="store_true", help="Fail unless every named module is present and all tests pass without skips")
    parser.add_argument("--report", type=Path, help="Write counts and relative test names only; never logs or local data")
    parser.add_argument("--worker", nargs=3, metavar=("TEST", "OUTPUT", "TEMP"), help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.worker:
        return worker(*args.worker)
    present, missing = select_tests(ROOT)
    syntax = []
    for name in (*PYTHON_FILES, *present):
        path = ROOT / name
        if not path.is_file():
            syntax.append(dict(file=name, status="MISSING")); continue
        try:
            ast.parse(path.read_bytes(), filename=name)
            syntax.append(dict(file=name, status="PASS"))
        except SyntaxError:
            syntax.append(dict(file=name, status="FAIL"))
    for name in SHELL_FILES:
        result = subprocess.run(["/bin/bash", "-n", str(ROOT / name)], capture_output=True, timeout=10)
        syntax.append(dict(file=name, status="PASS" if result.returncode == 0 else "FAIL"))
    try:
        # JSON is a YAML subset: this workflow needs no third-party parser/install.
        workflow = json.loads((ROOT / WORKFLOW).read_text(encoding="utf-8"))
        if not isinstance(workflow.get("jobs"), dict) or "push" not in workflow.get("on", {}):
            raise ValueError("Invalid workflow structure")
        syntax.append(dict(file=WORKFLOW, status="PASS"))
    except (OSError, ValueError):
        syntax.append(dict(file=WORKFLOW, status="FAIL"))
    results = []
    worker_env = {"PATH": "/usr/bin:/bin", "PYTHONIOENCODING": "utf-8"}
    node = shutil.which("node")
    if node:
        worker_env["U1_RELEASE_NODE"] = node
    javascript = []
    with tempfile.TemporaryDirectory(prefix="u1-personal-release-") as temporary:
        for index, name in enumerate(present):
            folder = Path(temporary) / str(index)
            folder.mkdir(mode=0o700)
            output = folder / "result.json"
            command = [sys.executable, "-I", "-B", str(Path(__file__).resolve()), "--worker", name, str(output), str(folder)]
            process = subprocess.Popen(command, cwd=str(ROOT), env=worker_env, start_new_session=True)
            try:
                returncode = process.wait(timeout=90)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
                returncode = -1
            if output.is_file():
                record = json.loads(output.read_text(encoding="utf-8"))
                if returncode != 0 and record["status"] == "PASS":
                    record["status"] = "FAIL"
            else:
                record = dict(file=name, status="FAIL", tests=0, failures=0, errors=1, skipped=0,
                              reason="timeout" if returncode == -1 else "worker-exited")
            results.append(record)
            print("{status}: {file} ({tests} tests, {skipped} skipped)".format(**record), flush=True)
            for identifier in record.get("opt_in_not_run", []):
                print("OPT-IN NOT_RUN: " + name + ":" + identifier, flush=True)
        for source in JS_SYNTAX_FILES:
            path = ROOT / source
            if not node or not path.is_file() or path.is_symlink():
                syntax.append(dict(file=source, status="FAIL"))
                continue
            try:
                checked = subprocess.run([node, "--check", str(path)], capture_output=True, timeout=10,
                                         env={"PATH": "/usr/bin:/bin", "HOME": temporary, "TMPDIR": temporary})
                syntax.append(dict(file=source, status="PASS" if checked.returncode == 0 else "FAIL"))
            except (OSError, subprocess.TimeoutExpired):
                syntax.append(dict(file=source, status="FAIL"))
        for index, name in enumerate(JS_TESTS):
            folder = (Path(temporary) / ("js-" + str(index))).resolve()
            folder.mkdir(mode=0o700)
            record = dict(file=name, status="FAIL", tests=0, failures=0, errors=1, skipped=0)
            try:
                js_command(name, ROOT, node)  # Validate every explicitly listed source before copying.
                for relative in (name, *JS_TESTS[name]):
                    staged = folder / relative
                    staged.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(ROOT / relative, staged)
                command = js_command(name, folder, node)
                env = {"PATH": "/usr/bin:/bin", "HOME": str(folder), "TMPDIR": str(folder)}
                if name == "tests/test_u1_operational_navigation.cjs":
                    shim = navigation_preload(folder, env)
                    command[1:1] = ["--require=" + str(shim), "--allow-fs-read=" + str(shim)]
                version = subprocess.run([node, "--version"], capture_output=True, text=True, timeout=10, env=env)
                if version.returncode or int(version.stdout.strip().lstrip("v").split(".")[0]) < 26:
                    raise ValueError("The guarded JavaScript checks require Node 26 or later")
                for source in (name, *JS_TESTS[name]):
                    if Path(source).suffix not in {".js", ".cjs", ".mjs"}:
                        continue
                    check = subprocess.run([node, "--check", str(ROOT / source)], capture_output=True, timeout=10, env=env)
                    syntax.append(dict(file=source, status="PASS" if check.returncode == 0 else "FAIL"))
                completed = subprocess.run(command, cwd=str(folder), env=env, capture_output=True, text=True, timeout=45)
                record = javascript_result(name, completed.returncode, completed.stdout)
                if record["status"] != "PASS":
                    print(completed.stdout + completed.stderr, file=sys.stderr)
            except (OSError, ValueError, subprocess.TimeoutExpired) as error:
                record["reason"] = type(error).__name__
                print(name + ": " + str(error), file=sys.stderr)
            javascript.append(record)
            print("{status}: {file} ({tests} tests, {skipped} skipped)".format(**record), flush=True)
    syntax_failed = any(item["status"] == "FAIL" for item in syntax)
    missing_syntax = [item["file"] for item in syntax if item["status"] == "MISSING"]
    status = result_status(results + javascript, missing + missing_syntax, syntax_failed)
    revision = os.environ.get("GITHUB_SHA", os.environ.get("U1_SOURCE_REVISION", ""))
    report = dict(schema_version=1, checked_at_utc=datetime.now(timezone.utc).isoformat(),
                  status=status, require_all=args.require_all,
                  source_revision=revision if re.fullmatch(r"[0-9a-f]{40,64}", revision) else "unrecorded",
                  tests_run=sum(item["tests"] for item in results + javascript), modules=results,
                  python_tests_run=sum(item["tests"] for item in results), javascript=javascript,
                  javascript_tests_run=sum(item["tests"] for item in javascript),
                  missing_tests=missing, syntax=syntax, native_build="NOT_RUN",
                  interactive_mac_checks="NOT_RUN", notarization="NOT_PERFORMED")
    if args.report:
        with args.report.open("x", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)
            handle.write("\n")
    for name in missing:
        print("MISSING: " + name)
    for item in syntax:
        if item["status"] != "PASS":
            print("SYNTAX {status}: {file}".format(**item))
    print("{}: {} Python tests and {} JavaScript tests; {} of {} named Python modules present. Native build, real FFmpeg and interactive Mac checks are separate.".format(status, report["python_tests_run"], report["javascript_tests_run"], len(present), len(TEST_FILES)))
    return 1 if status == "FAIL" or (args.require_all and status != "PASS") else 0


if __name__ == "__main__":
    raise SystemExit(main())
