# Account usage widget

The persistent usage widget reports **used percent**, not remaining percent.
The tooltip explains the remaining allowance, window duration and reset time.

## Correct bucket selection

Codex can return multiple metered buckets from `account/rateLimits/read`.
The general `codex` bucket and separate model buckets such as Spark must not be
combined or selected by response order. The backend preserves `limit_id`; the
widget selects the general bucket explicitly. The detail view retains each
window separately. The legacy single-bucket response remains supported.

This fixes a display defect where a separate model's zero-percent allowance
could incorrectly appear as the general Codex allowance.

Source contract: [OpenAI app-server documentation](https://learn.chatgpt.com/docs/app-server).

## Honest unavailable states

- Unknown, invalid, expired or stale usage displays `--`, never a fabricated zero.
- A real numeric zero remains valid.
- Snapshots expire after two minutes, using both receipt and provider check time.
- Claude and Antigravity local activity does not imply access to subscription quotas.
- Signing into one provider does not merge its allowance with another provider.
- Reading usage does not spend a reset credit or buy API credits.

## Isolated regression checks

`tests/test_u1_usage_windows.py` covers normalization without launching the
server or account client. `tests/test_u1_usage_selection.cjs` covers model-bucket
selection, unavailable states, reset expiry and snapshot freshness.
