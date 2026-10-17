# Bluetooth and measurement troubleshooting

[한국어](troubleshooting.ko.md) · [Home](../README.md)

Start with [shared proxy setup, recommended boards and connection checks (한국어)](https://github.com/eigger/hass-repo-standards/blob/main/docs/bluetooth.md). This includes XIAO W5500 V1.2 (Ethernet/PoE/external antenna) and the USB-A dongle-form M5Stack AtomS3U, purchase links and board-specific limitations. These recommendations do not claim new Atflee hardware validation.

## Find the failing stage

The scale normally turns its radio off while asleep. Briefly step on it, check its battery and keep it awake through setup and weighing. Close the official Atflee/Fitdays app and any other BLE clients. If a phone retains the connection, forget its pairing. This integration does not ask you for an account, password or universal bonding key; do not invent pairing steps for an unverified model.

Advertisement discovery only proves reception. GATT needs an HA-managed connectable adapter or an active proxy connection (`bluetooth_proxy.active: true`). `esp32_ble_tracker.scan_parameters.active` requests scan responses and is a different setting; leave interval/window at their defaults initially. A nearby proxy is useful; replacing an already working local adapter is optional.

| Failure or observation | Atflee-specific next step |
|---|---|
| Never discovered | Wake the scale, confirm the proxy is online in HA and move it closer. Manifest discovery matches `iGripX*` with service `0000ffb0-0000-1000-8000-00805f9b34fb`; a different model may need investigation. |
| `connect` | Sleeping scales commonly cannot connect. If an awake weigh-in never connects, release other apps, check actual adapter/proxy path, power/network and free connection slots. |
| `arm` | The link connected but measurement start/user-info preparation failed. Verify height, birth date and sex; report the error and model rather than repeatedly changing proxy scan timing. |
| `measure` | A packet could not be processed after connection. Save the error and a redacted packet reproduction; this is distinct from discovery. |
| Peer disconnect / link loss / write timeout | Keep the scale awake; check distance, battery, proxy power/network and simultaneous connections. Repair the route before retrying. A write timeout and a normal end-of-measurement idle timeout are different. |
| Weight absent from user | Add at least one user, inspect active/default user and weight references/tolerances. An unassigned measurement may fire `atflee_unassigned_measurement` rather than update anyone. See [attribution](usage.md#multiple-users). |
| Body composition absent | Check profile, supported model, body-composition switch and actual packets. Missing metrics are created only after a value is received. The profile sent on connect may differ from the final matched user; see [usage](usage.md). |
| Status looks unknown or `other` | Only Measure Status code 1 is understood (`weighing`); inspect `raw`. Verify/Scale Status codes are not known and new entries disable these sensors by default. Do not interpret them as verified device errors. |

## Use the diagnostics that actually exist

On the **scale device**, inspect **Connection Duration** attributes for the last finished session, **Last Failure** attributes for the last failed session, and **Failure Count**. A running session withholds the previous finished report from the duration sensor. Inspect report fields when present: failed stage/detail, error/cause, adapter/proxy path and timing. Preserve the distinction between an observed connection path and a best-reception/uncertain path. User sensors hold their own measurement attributes; raw recent packet and connection details are on the scale device. Device model/firmware and electrode capabilities help identify unsupported variants. No integration diagnostics-download endpoint is provided.

To collect only the needed reproduction, temporarily configure:

```yaml
logger:
  default: warning
  logs:
    custom_components.atflee: debug
```

Restart/reload logging as appropriate, reproduce one awake measurement, then disable debug logging. Logs can contain raw packets, Bluetooth address, user profile and measurement data. Before public sharing, remove MAC/serial numbers, user names, birth dates, height/sex/weight/body data, raw payloads that encode them, internal addresses and secrets. Keep timestamps, stage/error and model/firmware when safe.

Report HA/integration/blesession versions (when known), scale model/firmware, proxy model/revision/firmware and local/Ethernet/Wi-Fi path, reproduction time, awake state, other app connections, failed stage and sanitized logs. Distinguish the last success from the failure and automated HA tests from physical-device checks. There are no BLE ESL-specific Retry Count or Debounce controls here.
