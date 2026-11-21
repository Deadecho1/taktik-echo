# Taktik Echo

Taktik Echo is a maintained fork of [Taktik](https://github.com/masterFuf/taktik-bot) for platform browsing and device interaction on real Android phones.
It supplies the platform implementation used by [Persona Engine](https://github.com/Deadecho1/persona-engine), whose repository is private.

## Responsibilities

Taktik Echo owns screen recognition, selectors, content extraction, account verification, navigation, action verification, gestures, typing, and evidence capture.
Persona Engine owns persona configuration, model decisions, interests, beliefs, learning, search intent, query coordination, scheduling, history, and exports.

Extend the existing Taktik platform readers and device helpers when adding a capability.
Keep platform interaction inside this repository and expose structured observations and supported actions to callers.

## Branches

| Branch | Contents |
| --- | --- |
| `main` | Maintained shared Phone implementation and verified Instagram and TikTok browsing used by Persona Engine and EchoSeek. |
| `feature/x-platform` | Shared platform implementation plus the ongoing X extension, paired with Persona Engine's branch of the same name. |

Persona Engine's `taktik-install.json` selects the exact tested commit and local dependency directory.
A branch name alone is not a reproducible dependency pin.
Upstream updates are merged from `masterFuf/taktik-bot` into this fork's `main`, then into active feature branches.
Completed feature branches are retired after their changes and consumer references have been merged.

## Browsing interface

On `main` and the maintained extension branches:

- `taktik.core.shared.phone_interaction.Phone` owns the device session, execution constraints, cancellation, diagnostics, and keyboard lifecycle. It reuses Taktik's existing device and input helpers.
- `taktik.core.shared.browsing` defines `PostObservation`, action results, and supported capabilities.
- Each platform's `ui/` modules interpret captured screen hierarchies; its `services/browsing/` modules navigate and verify outcomes.
- Instagram exposes `Instagram`; TikTok exposes `TikTok`; the X feature branch exposes `XBrowser` from the respective platform's `services.browsing` package.

Use the same Phone object throughout a session. Preserve device reservations, persona and device locks, deadlines, uncertainty handling, and cleanup.
The workspace's `phone_interaction.Phone` import is a compatibility reexport of this implementation.
See the [browsing guide](https://github.com/Deadecho1/taktik-echo/blob/main/docs/verified-browsing.md) and [X extension guide](https://github.com/Deadecho1/taktik-echo/blob/feature/x-platform/docs/verified-browsing.md).

## X extension status

The X branch supports account-verified For you and Following browsing, text-only post observations, and separate quote, media, and account metadata.
Watch and skip are enabled. Unsupported or ambiguous layouts stop browsing.

The X branch recognizes native Paid partnership disclosures separately from authored text.
X search, engagement, promoted-placement recognition, physical long-text traversal, human visual review, and real-model validation remain incomplete.
The maintained branch does not imply that every installed X layout is supported.

## Installation

### App version policy

Automation requires an exact pinned app version, checked on the selected phone at startup and relaunch.
The supported pins are TikTok `43.1.4` and `47.0.3`, and Instagram `410.0.0.53.71` and `447.0.0.55.81`.
Gmail, YouTube, Threads, and any other app without an explicit pin refuse automation.
An unsupported or unreadable version produces an error naming the app and allowed versions before app automation starts.
Stop and cleanup remain available.

Install one of the pinned builds and disable its automatic updates on the phone.
Taktik does not change the phone's update settings or adapt automatically to a newer app version.
Maintainers declare exact pins in `taktik/core/shared/device/apps.py` after validating the build.
The historical selector families in [COMPATIBILITY.md](COMPATIBILITY.md) do not authorize other builds.

### Tested on

Recorded validation covers real Pixel 3a and Pixel 6a phones.
The pinned reference builds are TikTok `43.1.4` and Instagram `410.0.0.53.71`; the newer validated builds are TikTok `47.0.3` and Instagram `447.0.0.55.81`.
See [COMPATIBILITY.md](COMPATIBILITY.md) for each build's recorded phone, ABI, language, evidence, and known limits.
Emulators are not tested.

### Setup

For Persona Engine, run its `scripts/install_taktik.py` and install the resulting pinned checkout into that workspace's environment.
The checkout lives at `vendor/taktik-echo`.

For standalone development of the shared platform implementation:

```bash
git clone --branch main https://github.com/Deadecho1/taktik-echo.git
cd taktik-echo
python3 -m venv .venv
.venv/bin/python -m pip install --constraint requirements.lock --editable .
```

Select `feature/x-platform` before installing when working on X.
The Python distribution remains `taktik-bot`, the import package remains `taktik`, and the CLI command remains `taktik` for compatibility.
Android device operations require the appropriate local tools, USB authorization, and signed-in platform accounts.

## Validation and contributions

Use captured XML with its recorded screen dimensions, parser records, and replays through the Phone interface for implementation diagnostics.
Keep live-feed screenshots and contact sheets local, preserve raw evidence, and track human visual review separately from XML checks.
Do not bypass the shared Phone implementation with direct device operations.

Tests for the shared Phone implementation live in `tests/unit/shared/test_phone_interaction_session.py`.
Persona Engine also carries browsing and integration regression tests, including its ownership checks in `tests/test_phone_architecture.py`.
Publish and test changes to this fork before advancing Persona Engine's dependency pin.

## Upstream and license

This fork retains Taktik's [GNU GPL v3 license](LICENSE) and upstream attribution.
See the [upstream README](https://github.com/masterFuf/taktik-bot/blob/main/README.md) for the broader upstream CLI, desktop product, supported workflows, and documentation.
