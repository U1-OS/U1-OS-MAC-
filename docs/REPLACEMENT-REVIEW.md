# Replacement pull request: reviewer guide

## What is being proposed

This pull request proposes the local cinematic U1 OS rebuild as the replacement
application tree. It is **not** an attempt to combine every feature from the
separate v2.5.0 Wave 10 implementation on `main`.

The operator explicitly chose a replacement pull request after being informed
that the two implementations had unrelated Git histories. The review branch
joins both histories with a commit whose tree is the checked rebuild. This
allows a normal review against `main` without rewriting either history.

## Publication boundaries

- Creating the pull request does not merge it or change `main`.
- No force push, automatic merge or production deployment is part of this step.
- A repository front-page update is not a GitHub Pages deployment.
- Existing local accounts, vault contents, databases, exports and backups are
  not included as release artifacts.
- The local application remains available on its development branch.

## Review before merging

1. Review the complete file replacement, including removals relative to `main`.
2. Decide whether any Wave 10 workflow must be migrated into this rebuild before
   it replaces the default application. Feature parity is not assumed.
3. Back up real configuration and data separately. Do not copy a tracked
   configuration or vault from another implementation into this tree blindly.
4. Read the operational feature docs and distinguish offline functionality,
   tested adapters, setup-required providers and unavailable capabilities.
5. Complete account-specific acceptance with the operator's own consent.
6. Review the Mac wrapper's checkout dependency and ad-hoc signature limits.
7. Authorize merging and deployment separately after accepting the replacement.

## Evidence boundaries

The earlier cinematic baseline had a passing local release gate and hosted CI.
Those dated results do not establish that subsequent operational additions
passed. The pull request and operational documentation must report the latest
observed gate independently.

Fixture tests do not prove access to a signed-in external account. An installed
launcher is not proof that its service is running. An RSS or scoreboard adapter
must retain provider, timestamp, unavailable and stale states. A quota reading
does not merge separate provider subscriptions.

Read [the operational upgrade notes](OPERATIONAL-UPGRADE.md),
[usage widget contract](USAGE-WIDGET.md),
[Studio workflow](STUDIO-PRO.md),
[safety rehearsal](SAFETY-REHEARSAL.md), and
[media intake limitations](MEDIA-DOWNLOADS.md) before accepting the build.
