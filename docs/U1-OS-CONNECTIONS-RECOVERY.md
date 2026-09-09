# Connections, review and recovery

Updated 2026-09-08. Development implementation; real Google account acceptance
testing is still required. Provider subscriptions and limits remain separate.

## Google Connect

1. Build the owner-local helper: `bash macos/build-keychain.sh`.
2. Enable the Gmail and Google Calendar APIs in a Google Cloud project you control.
3. Configure OAuth consent and create a **Desktop app** OAuth client. Add your account as a test user if the project is in testing mode.
4. Open **Connections & recovery / Google Connect** in U1 OS.
5. Choose the Desktop OAuth client JSON and select **Save client to Keychain**.
6. Select **Sign in with Google**, follow the link in your system browser and review the read-only permissions.
7. Return to U1 OS and select **Sync now**. Only a successful service read establishes a verified snapshot.
8. Enable automatic sync or PDF import only if desired; both are off by default.

The flow uses a random localhost callback port, state binding and PKCE S256.
An in-progress sign-in cannot be replaced by another client. Credentials and
tokens use macOS Security, not browser storage, command-line arguments or a
plaintext fallback. macOS may request Keychain approval. See
[Google's installed-application OAuth guide](https://developers.google.com/identity/protocols/oauth2/native-app).

Scopes: `gmail.readonly` and `calendar.events.readonly`. This connector does not
send email, edit Google events, upload to Drive, call paid AI or perform trades.

## Bounded sync and review

- Email: the latest 20 messages from the past 14 days, excluding Spam and Trash. Not a full mailbox archive.
- Attachments: opt-in import of up to three PDFs per sync, each no larger than 5 MB.
- Extraction: existing text from the first ten pages, bounded to 12,000 characters; no OCR, script execution or remote model call.
- Important-message detection: a local heuristic creates review drafts. It can miss relevant messages and is not an emergency service.
- Calendar: up to 100 primary-calendar events from seven days ago to 90 days ahead. Coverage limitations are reported.
- Approval: explicit review creates/updates a local event; a provider update cannot silently overwrite a local edit.
- Cancellation: explicitly reported cancellations require approval before a local event moves to Trash. Absence from a bounded snapshot is not a cancellation.
- Reminders: approved local events use three-day, one-day, eight-hour and fifteen-minute stages while the server runs.
- Background sync: optional, approximately every five minutes while the server is running. Sleep, network failures and revoked permissions can delay it.

Emails, PDF text and event notes are untrusted data, never executable instructions.
Disconnect attempts revocation and removes the Keychain entry. Imported local
records and files remain. A client replacement clears the old provider snapshot
and bindings without deleting imported local records.

## Managed backups

Open **Workspace recovery**, select **Create managed backup** and review its
scope. Owner-only ZIP archives are stored in ignored `data/recovery/backups/`.

Included: the managed SQLite database, local records/preferences/business data,
imported file contents and managed Trash. Active imports must finish first;
failed imports may be moved to Trash so they do not block backups.

Excluded: Keychain tokens, `config.json`, other plugin or OSINT stores, source,
native binaries, remote-only Drive files and unrelated folders on the Mac.

**Archives are not encrypted.** They can contain private email and documents.
Owner-only permissions do not replace FileVault, secure accounts or encryption
for exported copies. Never upload these archives to the source repository.

## Isolated restore

Choose **Restore to a separate folder**. U1 OS checks member paths/counts,
size bounds, SHA-256 checksums and SQLite integrity, then creates a new folder
under `data/recovery/restores/`. The running database is never overwritten or
automatically switched. This is a recovery copy for inspection, not active
rollback, a full-Mac restore, cloud backup or a signed application update.

## Local API

| Route | Purpose |
| --- | --- |
| `GET /api/workspace/google` | Connection/snapshot/job status; no unsolicited Keychain read |
| `POST /api/workspace/google` | Configure, connect, sync, preferences, reviewed event or disconnect |
| `GET /api/workspace/recovery` | Archive inventory, coverage and job status |
| `POST /api/workspace/recovery` | Confirmed background backup or isolated restore |

Writes retain same-origin and `X-U1-CSRF` checks. This remains a localhost
development application, not a hardened multi-user hosting service.
