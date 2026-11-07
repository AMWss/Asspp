# Free Apple ID signing

This directory owns the headless signer and GitHub Actions support scripts.
Use the pinned isideload revision in Cargo.toml. Never log credentials, session
plists, certificate keys, provisioning profiles or verification codes. Persist
signing state only through authenticated encryption. Certificate exhaustion
must fail without revoking certificates. Run Python tests and cargo check before
publishing changes. Real Apple authentication and device execution require user
validation and must be reported separately from offline checks.
