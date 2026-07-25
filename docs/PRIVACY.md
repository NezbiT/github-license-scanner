# Privacy policy — GitHub License Scanner

**Effective date:** 2026-07-24  
**Data controller (self-hosted):** the operator who runs this instance.

This Tool is primarily designed for **local / self-hosted** use. If you deploy it as a multi-user service, **you** become responsible for providing a complete privacy notice to your users under applicable law (e.g. GDPR, CCPA/CPRA, UK GDPR).

## Data we process

| Data | Purpose | Storage | Retention |
|------|---------|---------|-----------|
| GitHub repo URLs you submit | Run license analysis | In memory during scan; may be written to local history | See history settings |
| Scan results (owner/repo, license ids, risk flags, short verdict text) | History UI / CLI | `data/history.json` on the host | Max entries + optional max age (default 90 days) |
| UI preferences (language, theme) | UX | Browser cookie / NiceGUI user storage (signed) | Browser session / cookie lifetime |
| Rate-limit counters | Abuse prevention | In-process memory | Rolling window (default 1 hour) |
| Optional `GITHUB_TOKEN` | Higher GitHub API limits / private repos | Environment of the host process only | Until you remove it |

The Tool **does not intentionally collect** names, emails, payment data, or government IDs.

## Third-party processing

When you run a scan, the host machine sends requests to:

- **api.github.com** — repository metadata and file contents  
- Package registries as needed (e.g. **registry.npmjs.org**, **pypi.org**, **crates.io**, **rubygems.org**, **repo.packagist.org**)

Those services process the request under **their** privacy policies and terms. Do not submit private repository URLs unless you are authorized and understand that API tokens and network logs may retain metadata.

## History isolation

| Mode | Path | Visibility |
|------|------|------------|
| Auth **disabled** (default) | `data/history.json` | Shared by everyone on the instance |
| Auth **enabled** (`GLS_AUTH_ENABLED=1`) | `data/history/<username>.json` | Isolated per logged-in user |

On a multi-user deployment **without** authentication, any user of that instance can see others’ recent scans. Enable auth (create users with `python cli.py user-add …`) for per-user isolation.

## Your rights (GDPR / CCPA-style)

If EU/UK GDPR or similar laws apply to **your** deployment:

| Right | How to exercise on this Tool |
|-------|------------------------------|
| Access | Read `data/history.json` / History tab |
| Erasure | Use **Clear history** in the UI, or delete `data/history.json` |
| Restriction / objection | Stop using the service; operator may disable history |
| Portability | Export Markdown report from a scan result |

Cookie/local storage for language and theme is used for **strictly necessary / preference** purposes on this self-hosted UI.

## Security measures (baseline)

- Default bind address `127.0.0.1` (local only)  
- Configurable session signing secret (`GLS_STORAGE_SECRET`)  
- Scan rate limiting  
- Batch size caps  
- History retention limits  
- No hardcoded production secrets (see `.env.example`)

Operators should still place TLS, access control, and log hygiene in front of any public deployment.

## Children

The Tool is not directed at children under 16 (or the age required in your jurisdiction).

## Contact

For the public open-source project, open an issue on the GitHub repository.  
For a **self-hosted** instance, contact the organization that runs the server.
