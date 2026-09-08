# U1 integrations

The integration registry is `/api/integrations`. Its saved fields and included
adapters are configuration metadata, not proof of authentication. The canonical
Home labels them **Settings saved / unverified** or **Connection required**.

The initial boot deliberately reports AI/provider access as needing an
authorised provider. It does not call billable models, inspect browser session
cookies or fan private content out to several AI companies.

Existing account configuration, provider adapters, CSRF checks and local
terminal are preserved. Integration setup is hosted inside the outer OS shell.
External OAuth pages may still require the provider's supported browser flow.

Readiness probes verified registry and local-data API responses, not individual
OpenAI, Claude, Antigravity, Canva, Gmail, Drive or calendar accounts. Quotas are
not merged. There are no authentication, DRM or security bypasses.
