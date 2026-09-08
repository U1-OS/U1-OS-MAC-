"""Local bundle metadata and reversible promotion; no downloading or source updates."""
import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import plistlib
import re
import shutil
import subprocess
import tempfile
import uuid

BUNDLE_ID = "local.u1os.business"


def metadata(root, version="2.1.0", build="1", revision="unrecorded"):
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("Version must use major.minor.patch numbers")
    if not re.fullmatch(r"\d{1,4}(?:\.\d{1,2}){0,2}", build):
        raise ValueError("Build must be a CFBundleVersion, for example 1 or 2609.8.1")
    if revision != "unrecorded" and not re.fullmatch(r"[0-9a-f]{40,64}", revision):
        raise ValueError("Source revision must be a full hexadecimal commit ID")
    return dict(CFBundleExecutable="U1OS", CFBundleIdentifier=BUNDLE_ID,
                CFBundleName="U1 OS", CFBundleDisplayName="U1 OS",
                CFBundlePackageType="APPL", CFBundleShortVersionString=version,
                CFBundleVersion=build, CFBundleIconFile="U1.icns",
                LSMinimumSystemVersion="12.0", NSHighResolutionCapable=True,
                NSAppTransportSecurity={"NSAllowsLocalNetworking": True},
                U1WorkspaceRoot=str(Path(root).resolve()), U1SourceRevision=revision,
                U1Distribution="local-workspace-dependent-ad-hoc")


def require_bundle(path):
    path = Path(path)
    if path.is_symlink() or not path.is_dir():
        raise ValueError("Expected a real U1 OS application directory")
    info = path / "Contents" / "Info.plist"
    if info.is_symlink() or (path / "Contents").is_symlink():
        raise ValueError("Refusing redirected bundle metadata")
    with info.open("rb") as handle:
        if plistlib.load(handle).get("CFBundleIdentifier") != BUNDLE_ID:
            raise ValueError("Refusing to replace an unrelated application")


def promote_bundle(staged, destination, replace=False):
    """Same-volume rename, with an intact backup and rollback on promotion failure."""
    staged, destination = Path(staged), Path(destination)
    require_bundle(staged)
    if destination.is_symlink() or destination.parent.is_symlink():
        raise ValueError("Refusing a symlinked destination")
    backup = None
    if destination.exists():
        if not replace:
            raise FileExistsError("Explicit replacement permission is required")
        require_bundle(destination)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = destination.with_name(destination.stem + ".backup-" + stamp + "-" + uuid.uuid4().hex[:8] + ".app")
        destination.rename(backup)
    try:
        staged.rename(destination)
    except OSError:
        if backup is not None:
            backup.rename(destination)
        raise
    return backup


def install_bundle(app, desktop, replace=False):
    desktop = Path(desktop)
    if desktop.is_symlink() or not desktop.is_dir():
        raise ValueError("Desktop must be an existing real directory")
    destination = desktop / "U1 OS.app"
    lock = desktop / ".u1-desktop-install.lock"
    lock.mkdir(mode=0o700)
    try:
        if destination.exists() and not replace:
            raise FileExistsError("Desktop replacement requires --replace-desktop")
        require_bundle(app)
        with tempfile.TemporaryDirectory(prefix=".u1-install-", dir=str(desktop)) as temporary:
            staged = Path(temporary) / "U1 OS.app"
            shutil.copytree(app, staged, symlinks=True)
            subprocess.run(["/usr/bin/codesign", "--verify", "--strict", str(staged)], check=True, timeout=30)
            return promote_bundle(staged, destination, replace=replace)
    finally:
        lock.rmdir()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("metadata", "promote", "install"))
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--replace-desktop", action="store_true")
    args = parser.parse_args()
    if args.operation == "metadata":
        info = metadata(args.destination, os.environ.get("U1_DESKTOP_VERSION", "2.1.0"),
                        os.environ.get("U1_DESKTOP_BUILD_ID", "1"), os.environ.get("U1_SOURCE_REVISION", "unrecorded"))
        with (args.source / "Contents" / "Info.plist").open("wb") as handle:
            plistlib.dump(info, handle)
        return
    if args.operation == "install":
        backup = install_bundle(args.source, args.destination, replace=args.replace_desktop)
    else:
        backup = promote_bundle(args.source, args.destination, replace=True)
    if backup:
        print("Previous application preserved:", backup)


if __name__ == "__main__":
    main()
