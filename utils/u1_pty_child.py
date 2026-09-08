"""Become the controlling process of an already-open PTY, without preexec_fn."""
import fcntl
import os
import sys
import termios

if __name__ == "__main__":
    os.setsid()
    fcntl.ioctl(0, termios.TIOCSCTTY, 0)
    shell = sys.argv[1]
    os.execv(shell, [shell, "-il" if shell.endswith("zsh") else "-i"])
