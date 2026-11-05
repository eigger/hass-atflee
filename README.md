<!-- hass-standards:header:start -->
# Atflee BLE for Home Assistant

A Home Assistant custom integration that reads Atflee BLE scales directly, with per-user weight, body composition and connection diagnostics.

**English** | [한국어](README.ko.md)

<!-- hass-standards:badges:start -->
[![Release](https://img.shields.io/github/v/release/eigger/hass-atflee?style=flat)](https://github.com/eigger/hass-atflee/releases)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5?style=flat)](#installation)
[![Home Assistant minimum](https://img.shields.io/badge/HA-%E2%89%A5%202025.8.0-41BDF5?style=flat)](hacs.json)
[![Tests](https://img.shields.io/github/actions/workflow/status/eigger/hass-atflee/tests.yml?branch=master&style=flat&label=Tests)](https://github.com/eigger/hass-atflee/actions/workflows/tests.yml)
[![Validate](https://img.shields.io/github/actions/workflow/status/eigger/hass-atflee/validate.yml?branch=master&style=flat&label=Validate)](https://github.com/eigger/hass-atflee/actions/workflows/validate.yml)
[![License](https://img.shields.io/github/license/eigger/hass-atflee?style=flat)](LICENSE)
[![Downloads](https://img.shields.io/github/downloads/eigger/hass-atflee/latest/total?style=flat&color=41BDF5&label=Downloads)](https://github.com/eigger/hass-atflee/releases)
<!-- hass-standards:badges:end -->
<!-- hass-standards:header:end -->

The Downloads badge counts attached asset downloads for the latest GitHub release. It does not measure active installations.

## Supported devices

- Atflee iGrip family (including iGripX and iGrip Pro).
- Atflee T8 and other protocol-compatible models **may work; untested**.

## Features

- Separate user profiles, weight-based attribution, an active-user select and a body-composition switch. Available metrics depend on the device and received packets.

## Requirements

- **Home Assistant:** 2025.8.0 or later.
- **Bluetooth:** An HA-managed Bluetooth adapter or a Bluetooth proxy that supports active GATT connections.
- **Device:** A supported scale from [Supported devices](#supported-devices).

## Installation

<!-- hass-standards:installation:start -->
[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=eigger&repository=hass-atflee&category=integration)
<!-- hass-standards:installation:end -->

1. Click the badge above to open the repository in Marketplace.
2. If you need to add it yourself, go to **Settings → Marketplace → Add from link** and enter <https://github.com/eigger/hass-atflee>. Connect GitHub if prompted.
3. Select **Install**. Restart Home Assistant if prompted, then continue to [Configuration](#configuration).

## Configuration

Briefly step on the scale to wake it, and keep it awake during setup and measurement. Close any other app using it.

1. Open **Settings → Devices & services → Add integration → Atflee**, or configure its Bluetooth discovery.
2. Enter the first user's name, height, birth date (`YYYY-MM-DD`), sex and optional expected weight. Remain on the scale until the measurement finishes.

## Quick start

1. Add a second user through **Add user**.
2. Select that user under **Active user** before weighing.

The selection returns to `auto` after one completed measurement or 10 minutes. See [user attribution and all entities](docs/usage.md).

## Important limitations

- Consumer body-composition and evaluation values are estimates, **not medical advice**; some formula scales have not been verified against other devices.
- For installs upgraded from **0.3.2 or earlier**, add a user before any weight can be recorded; old profiles are not migrated. [Upgrade steps](docs/usage.md#upgrading-from-032-or-earlier-no-migration).
- Bluetooth discovery does not guarantee a GATT connection. Close the official app; if necessary, forget the phone's pairing. A working local adapter is supported; a nearby Bluetooth proxy can improve placement. [Bluetooth proxy setup](https://github.com/eigger/blesession/blob/main/docs/bluetooth.md) · [Troubleshooting](docs/troubleshooting.md).
- No new physical-device, firmware or proxy-board validation was performed during standards adoption.

## Documentation

| Guide | Contents |
|---|---|
| [Usage and configuration](docs/usage.md) / [한국어](docs/usage.ko.md) | Profiles, attribution, entities, evaluation ranges, legacy upgrade |
| [Troubleshooting](docs/troubleshooting.md) / [한국어](docs/troubleshooting.ko.md) | Waking the scale, proxy/GATT failures, actual diagnostics and private data |
| [Development and tests (한국어)](docs/development.md) | Core-like layout, real HA tests, separate minimum/current environments |
| [Standards adoption (한국어)](STANDARDS.md) | Reviewed rules, checklist and verification limits |

Remove personal profiles, measurements, addresses and secrets before sharing logs.

<!-- hass-standards:support:start -->
## Support

- [Issues](https://github.com/eigger/hass-atflee/issues): Report bugs or request features.
- [Discussions](https://github.com/eigger/hass-atflee/discussions): Ask questions and share your experience.
<!-- hass-standards:support:end -->

<!-- hass-standards:related-projects:start -->
<!-- hass-standards:related-projects:end -->

<!-- hass-standards:license:start -->
## License

Released under the [MIT License](LICENSE).
<!-- hass-standards:license:end -->
