# U1 OS safety lock

## What it protects

The local server gates new `/api/` GET and POST requests when locked, with only
the safety endpoint available for status, configuration and unlocking. The
canonical shell conceals its content, makes its shell inert, pauses its local
HTML media and cancels browser speech output. Other open U1 OS windows learn the
server state on a five-second poll. This is application access control, not data
encryption or a defence against someone who controls the Mac account or source.

**Existing background jobs, already-open streams, actions admitted before the
lock, trading orders and other applications are not cancelled.** This is not a
network firewall, FileVault, a Mac lock screen or an emergency system. No files
are wiped and no external accounts are disconnected by the switch.

## Setup

1. Open U1 OS and select Set up safety in the top controls.
2. Choose and confirm a passphrase of 10 to 128 characters.
3. Choose offline locking and, optionally, a timed check-in interval.
4. Read and confirm the scope, then save. Saving immediately locks U1 OS.
5. Unlock using the passphrase. If offline locking is enabled, HTTPS reachability
   must succeed before unlocking.

Nothing is armed until setup succeeds. Passwords are not collected in chat or
stored in browser preferences. The server stores only a random salt, a scrypt
hash and settings in owner-only `data/safety/state.json`. The directory is local
runtime data and must not be committed. Five failed passphrase attempts impose
a 60-second delay within the running server.

## Triggers

- Lock now in Safety Centre.
- Command or Control + Shift + L, while the U1 OS window has keyboard focus.
- An enabled check-in timer expires. Only an explicit operator check-in or
  successful unlock resets it. Background polling does not count as activity.
- With offline locking enabled, two server reachability probes fail, or the
  browser reports an offline event.
- The server restarts after safety has been configured.
- The UI loses the local safety service after setup: it conceals locally and
  requests the backend lock when communication resumes.

The watchdog attempts credential-free HTTPS HEAD requests to
`https://www.gstatic.com/generate_204` and
`https://cp.cloudflare.com/generate_204`. It requires an exact 204 response,
validates TLS and does not follow redirects. Probes run approximately every
12 seconds, plus bounded connection time. Filters, captive portals or blocked
probe hosts can cause a lock even when other internet access works. This checks
reachability, not whether a connection is secure or a VPN is active.

Reconnection never automatically unlocks the OS. To use the OS deliberately
offline, open Safety settings from the lock screen, authenticate, disable
offline locking and save. A separate passphrase unlock is still required.

## Recovery and limits

There is no browser reset or unauthenticated override. An unreadable safety
configuration fails closed. If the passphrase is lost, the Mac account owner
must perform a deliberate local recovery while the server is stopped. Preserve
a private backup before changing any runtime files; this release does not
automate that recovery. Managed workspace backups do not include the passphrase
configuration unless separately documented.

The focused-window shortcut is not a global macOS hotkey. No physical dead-man
device has been installed. Timers and probes require the local process to run;
sleep, power failure and network loss can delay checks or alerts. All safety
behaviour in this source increment still requires validation before reliance.
