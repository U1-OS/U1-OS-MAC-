# U1 OS Agent Centre

Open **Agent Centre** in the OS sidebar. Four advisers share a local evidence
history, feedback ranking and optional, explicitly requested Ollama analysis.

| Agent | Implemented capability | Important boundary |
| --- | --- | --- |
| Systems engineer | Reads the existing maintenance adviser's real findings | Does not repair or install software |
| Design director | Checks selected SVG geometry and current-page measurements | Not a full visual or accessibility audit |
| Trading researcher | Identifies missing market evidence and research prerequisites | No broker feed, positions, backtests or orders |
| Crypto analyst | Retrieves public BTC, ETH and SOL USD spot snapshots | No wallet access, trading, forecasts or profit claims |

## What self-improvement means here

Useful/lower-priority feedback is persisted per finding and run. Subsequent
checks use accumulated feedback to rank suggestions. Attention findings retain
priority. This is feedback-based ranking, not model retraining, profitability
learning or autonomous source-code rewriting. The agents cannot expand their
own permissions. The old simulated crypto module is not used as evidence.

## Operation

- Checks are manual by default. Each agent has an explicit 15-minute monitoring
  toggle; monitoring only runs while the local U1 OS server is running.
- Automatic checks never invoke AI. Optional model reviews require a discovered
  Ollama model and a separate user action. Account subscriptions are not assumed
  connected or merged. No provider credentials are read by this module.
- Public spot quotes include retrieval timestamps and are labelled snapshots,
  not streaming prices or executable quotes. Unavailable feeds remain missing.
- State is in `data/agent-centre/agents.sqlite3`, owner-readable/writable, and
  excluded from source publication. History is capped at 200 runs; the UI shows
  the most recent 40 across agents. Feedback for expired runs expires with them.
- POST requests use the existing OS CSRF and origin checks. External endpoints
  are fixed, requests are bounded, redirects and environment proxies disabled.
- No command execution, code changes, publishing, email access, trading or
  wallet endpoint exists in this module.

## Source references

- [Coinbase public price API](https://docs.cdp.coinbase.com/coinbase-app/track-apis/prices)
- [Ollama generation API](https://docs.ollama.com/api/generate)
- [Ollama model discovery](https://docs.ollama.com/api/tags)

## Local checks

```sh
.runtime/bin/python3 -m unittest discover -s tests -p 'test_u1_agent_centre.py'
node --check static/js/u1-agent-centre.js
```

AI reviews remain unverified until an available model completes a real review.
Before any future order integration, separately define broker permissions,
position limits, order confirmation, audit records and a kill switch.
