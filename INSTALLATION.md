# U1 OS local installation

## New checkout

Use macOS with Python 3.11 or newer. In the repository folder:

```sh
python3 -m venv .runtime
cp config.example.json config.json
chmod 600 config.json
./start-u1-os.command
```

Do not overwrite an existing configuration when updating. The runtime and credentials are deliberately not included in Git.

- Dashboard: `http://127.0.0.1:8788/`
- Integrations: `http://127.0.0.1:8788/integrations.html`
- Launcher: `start-u1-os.command`, or `U1 OS.app` kept inside the repository folder.
- The `.app` resolves its backend relative to this folder. It is not signed, notarized or a self-contained application installer.
- The older `command-center` CLI and some recovered helpers still assume port 8787. Use the new launcher for this installation.

## Existing installation

Keep `config.json`, `.runtime/`, `data/`, local exports and your third-party tool repositories. Restart your owned U1 OS server after backend changes; reload the browser for updated frontend assets. Do not stop unrelated processes merely because a port is occupied.

The launcher refuses to take over a port used by another installation. A stale `.u1-os.pid` alone is not proof of process ownership.

## Optional components

- Claude Code and Codex CLIs must be installed and signed in separately. A subscription website login does not automatically authorize a local CLI or API.
- Local OSINT launchers expect repositories under `~/Documents/ChatGPT/Repo's` and matching Desktop launcher configurations. These tools are not downloaded by this repository.
- FFmpeg and Ollama are separate optional runtimes. Ollama also needs a downloaded model.
- PDF-related components may require `reportlab` and `pypdf` in the Python environment. The requested full digital-product/PDF studio and automatic Gmail briefing workflows remain unfinished.
- Some integration entries are configuration slots or draft adapters, not active connections.

## Safety and data

Use the provided example configuration for a new setup. Setup mode keeps recovered crypto execution disabled. Do not enter wallet seed phrases or private keys.

`config.json`, casebook data and provider telemetry are local, owner-only files where configured, but are not encrypted by these forms. Do not publish runtime directories or raw exports. The source ignore rules are a safeguard, not a substitute for reviewing what you choose to share.

Public feeds can fail or be delayed. The stock watchlist is indicative, not a brokerage quote feed. Victoria weather warnings must not be your sole emergency-information source. The market clock's published holiday data currently covers 2026 only.

## Verification status

The current rebuild has not been fully validated in a browser or against every live provider. Do not run the inherited `tests/test_full_suite.py` as a casual startup check: it includes state mutation, system actions and outbound operations. Choose a deliberately scoped validation plan instead.
