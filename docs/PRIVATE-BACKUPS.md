# Private backup copies

The Security workspace adds explicit encrypted copies of managed backups and a
non-destructive restore drill. It does not encrypt the live workspace database
or remove existing plaintext archives.

## Cryptography and scope

- AES-256-GCM authenticated encryption using the installed cryptography library.
- A fresh 16-byte random salt and 12-byte random nonce for each copy.
- scrypt key derivation with N=32768, r=8, p=1 and a 32-byte output key.
- A versioned, authenticated U1 backup envelope.
- Operator-supplied passphrases of 12 to 128 characters, never persisted by this module.
- A 16 MiB source-archive limit to bound this local in-memory workflow.

This produces a new downloadable `.u1backup` file. The operator must keep the
passphrase separately; there is no recovery key or password reset. The original
managed archive remains unchanged and unencrypted. Existing managed recovery
coverage applies: credentials and unrelated plugin stores are not included.

## Restore drill

The operator selects an encrypted file and supplies its passphrase explicitly.
Authenticated decryption must succeed before ZIP and workspace validation. The
existing recovery validator checks the archive before restoring to a separate
private folder. The active database and managed files are not overwritten.
The temporary decrypted ZIP created by this operation is removed afterwards.
Restored contents are plaintext in the separate local folder and must be kept
private. This is a recovery exercise, not an automatic rollback or cloud sync.

## Validation

`tests/test_u1_private_backup.py` covers randomised authenticated round trips,
tamper and wrong-passphrase rejection, bounded inputs and confirmation, and a
real isolated managed-archive restore without replacing the active database.
