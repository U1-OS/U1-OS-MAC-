#!/usr/bin/env python3
"""
Command Center — macOS Process Resource Watchdog & Triage Sentinel
Monitors running processes, sorts by CPU/RAM usage, and provides guarded termination.
"""

import os
import sys
import subprocess
import signal
import time
from typing import Dict, Any, List

PROTECTED_NAMES = {
    "launchd", "kernel_task", "WindowServer", "loginwindow", "opendirectoryd",
    "kextd", "syslogd", "configd", "distnoted", "notifyd", "powerd"
}

def is_protected_pid(pid: int, name: str = "") -> bool:
    """Return True if the PID is critical to the OS or Command Center itself."""
    try:
        pid_int = int(pid)
    except (ValueError, TypeError):
        return True

    if pid_int <= 100:
        return True
    if pid_int == os.getpid() or pid_int == os.getppid():
        return True
    if name in PROTECTED_NAMES:
        return True
    return False

def get_top_processes(by: str = "cpu", limit: int = 15) -> List[Dict[str, Any]]:
    """
    Query top processes on macOS via native ps.
    by: 'cpu' (sort by %CPU) or 'mem' (sort by %MEM)
    """
    flag = "-r" if by.lower() == "cpu" else "-m"
    cmd = ["ps", "-A", "-o", "pid,ppid,%cpu,%mem,comm", flag]

    processes = []
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=4.0)
        lines = res.stdout.strip().splitlines()
        if len(lines) > 1:
            for line in lines[1:]:
                parts = line.strip().split(None, 4)
                if len(parts) >= 5:
                    pid_str, ppid_str, cpu_str, mem_str, comm_str = parts
                    try:
                        pid = int(pid_str)
                        ppid = int(ppid_str)
                        cpu = float(cpu_str)
                        mem = float(mem_str)
                    except ValueError:
                        continue

                    name = os.path.basename(comm_str.strip())
                    protected = is_protected_pid(pid, name)

                    processes.append({
                        "pid": pid,
                        "ppid": ppid,
                        "cpu_pct": cpu,
                        "mem_pct": mem,
                        "command": comm_str.strip(),
                        "name": name,
                        "is_protected": protected
                    })
                    if len(processes) >= limit:
                        break
    except Exception as e:
        processes = [{"error": str(e)}]

    return processes

def kill_process(pid: int, signal_name: str = "TERM", confirmed: bool = False, actor: str = "operator") -> Dict[str, Any]:
    """
    Safely terminate a rogue process.
    Requires confirmed=True.
    Refuses to kill protected PIDs (system daemons or Command Center itself).
    """
    try:
        target_pid = int(pid)
    except (ValueError, TypeError):
        return {"success": False, "error": "INVALID_PID", "message": f"Invalid PID: {pid}"}

    if not confirmed:
        return {
            "success": False,
            "error": "CONFIRMATION_REQUIRED",
            "message": f"Terminating PID {target_pid} requires explicit confirmation.",
            "pid": target_pid
        }

    # Verify if protected
    procs = get_top_processes(by="cpu", limit=100)
    target_name = ""
    for p in procs:
        if p.get("pid") == target_pid:
            target_name = p.get("name", "")
            break

    if is_protected_pid(target_pid, target_name):
        return {
            "success": False,
            "error": "PROTECTED_PROCESS",
            "message": f"PID {target_pid} ({target_name or 'System Task'}) is protected and cannot be terminated.",
            "pid": target_pid
        }

    sig = signal.SIGKILL if signal_name.upper() == "KILL" else signal.SIGTERM
    try:
        os.kill(target_pid, sig)
        # Log to ledger if available
        try:
            from utils.ledger import log_audit
            log_audit("watchdog", "terminate_process", f"Sent {signal_name.upper()} to PID {target_pid} ({target_name})", actor=actor)
        except Exception:
            pass

        return {
            "success": True,
            "pid": target_pid,
            "name": target_name,
            "signal": signal_name.upper(),
            "message": f"Successfully dispatched SIG{signal_name.upper()} to PID {target_pid} ({target_name})"
        }
    except ProcessLookupError:
        return {"success": False, "error": "NOT_FOUND", "message": f"Process {target_pid} does not exist"}
    except PermissionError:
        return {"success": False, "error": "PERMISSION_DENIED", "message": f"Insufficient permissions to terminate PID {target_pid}"}
    except Exception as e:
        return {"success": False, "error": "ERROR", "message": str(e)}

if __name__ == "__main__":
    print("=== TOP PROCESSES BY CPU ===")
    for p in get_top_processes("cpu", limit=8):
        print(f"PID {p['pid']:<6} CPU: {p['cpu_pct']:>5}%  MEM: {p['mem_pct']:>5}%  PROT: {str(p['is_protected']):<5}  NAME: {p['name']}")
