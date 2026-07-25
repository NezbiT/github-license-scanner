# Legal disclaimer — GitHub License Scanner

**Effective date:** 2026-07-24

## Not legal advice

GitHub License Scanner (“the Tool”) provides **automated heuristics** about open-source licenses detected in public (or token-accessible) GitHub repositories and package registries.

The Tool:

- is **not** a law firm, attorney, or licensed legal service;
- does **not** create an attorney–client relationship;
- does **not** issue formal license-compatibility opinions;
- does **not** warrant non-infringement, fitness for purpose, or merchantability;
- may produce **false positives and false negatives**.

**You must consult a qualified attorney** before commercial closed-source distribution, M&A diligence, or any high-stakes compliance decision.

## What the Tool does not fully model

Among other things, results may be incomplete or wrong regarding:

| Topic | Why it matters |
|-------|----------------|
| Static vs dynamic linking | GPL obligations often depend on how code is combined |
| SaaS / network use | AGPL and SSPL may impose duties without traditional “distribution” |
| Dual licensing / additional permissions | “MIT OR GPL” choice and exceptions change outcomes |
| Private patches & internal forks | History and LICENSE files may not reflect reality |
| System libraries & OS exceptions | Some jurisdictions/license texts have special rules |
| Patent, trademark, export, privacy law | Outside license text classification |
| Contracts / CLAs / ToS | Can override or add to open-source license terms |
| Transitive / lockfile-only deps | Not fully resolved from lockfiles in all ecosystems |
| Maven/Gradle/Go registry licenses | Often unresolved (unknown) |

## “Can sell closed” / “Forces open source”

These UI labels are **risk signals**, not legal conclusions. A green or “OK” result still requires:

1. Attribution and notice preservation (MIT, BSD, Apache-2.0, etc.).
2. Compliance with Apache-2.0 patent and NOTICE rules where applicable.
3. Review of each dependency’s full license text and any third-party notices.
4. Confirmation that build pipelines do not ship “dev-only” copyleft code.

## Copyright notice templates

Generated notices are **templates only**. The GitHub **owner or organization name is not proof of copyright ownership** (forks, employers, multi-author projects, work-for-hire). Always verify LICENSE, NOTICE, and authorship before use.

## No warranty / limitation of liability

THE TOOL IS PROVIDED “AS IS” AND “AS AVAILABLE”, WITHOUT WARRANTY OF ANY KIND. TO THE MAXIMUM EXTENT PERMITTED BY LAW, THE AUTHORS AND COPYRIGHT HOLDERS SHALL NOT BE LIABLE FOR ANY CLAIM, DAMAGES, OR OTHER LIABILITY ARISING FROM USE OF THE TOOL OR RELIANCE ON ITS OUTPUT.

See also the project [MIT License](../LICENSE).

## Related documents

- [Privacy](PRIVACY.md)
- [Terms of use](TERMS.md)
