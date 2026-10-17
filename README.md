# Atflee BLE Home Assistant Integration (hass-atflee)

[![GitHub Release](https://img.shields.io/github/v/release/eigger/hass-atflee?style=flat-square)](https://github.com/eigger/hass-atflee/releases)
[![License](https://img.shields.io/github/license/eigger/hass-atflee?style=flat-square)](LICENSE)
[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
![integration usage](https://img.shields.io/badge/dynamic/json?color=41BDF5&logo=home-assistant&label=usage&suffix=%20installs&cacheSeconds=15600&query=%24.atflee.total&url=https%3A%2F%2Fanalytics.home-assistant.io%2Fcustom_integrations.json)

<p align="center">
  <img src="https://raw.githubusercontent.com/eigger/hass-atflee/master/docs/images/scale.jpg" width="400" alt="Atflee Scale Integration">
</p>

A custom integration for Home Assistant to connect and poll data directly from Atflee Bluetooth Low Energy (BLE) body composition scales.

## 💬 Feedback & Support

🐞 Found a bug? Let us know via an [Issue](https://github.com/eigger/hass-atflee/issues).  
💡 Have a question or suggestion? Join the [Discussion](https://github.com/eigger/hass-atflee/discussions)!

## Supported Models

- **Atflee iGrip** (e.g., iGripX, iGrip Pro)
- **Atflee T8** (might work, untested)
- *Other Atflee BLE scales might work if they share the same protocol. If your device does not work, please share the debug logs for further investigation.*

## ⚠️ Warning: Conflict with Official App
**BLE scales often support limited simultaneous connections.**
If you have already paired your scale with the official Atflee (Fitdays/etc) smartphone app, you might need to **unpair/forget** the device from your phone's Bluetooth settings if you experience connection issues.

## Installation

1. **HACS**: Add this repository (`eigger/hass-atflee`) to HACS as a custom repository.
2. **Search**: Search for "Atflee" in HACS and install it.
3. **Restart**: Restart Home Assistant.
4. **Configure**: Go to Settings > Devices & Services > Add Integration > Atflee.

## ⚠️ Important Notice

- It is **strongly recommended to use a Bluetooth proxy instead of a built-in Bluetooth adapter**.  
  Bluetooth proxies generally offer more stable connections and better range, especially in environments with multiple BLE devices.

> [!TIP]
> For hardware recommendations, refer to [Great ESP32 Board for an ESPHome Bluetooth Proxy](https://community.home-assistant.io/t/great-esp32-board-for-an-esphome-bluetooth-proxy/916767/31).  
- When using a Bluetooth proxy, it is strongly recommended to **keep the scan interval at its default value**.  
  Changing these values may cause issues with Bluetooth data transmission.
- **bluetooth_proxy:** must always have **active: true**.

  Example (recommended configuration with default values):

  ```yaml
  esp32_ble_tracker:
    scan_parameters:
      active: true

  bluetooth_proxy:
    active: true
  ```
  
## Pairing & Configuration

Device setup and discovery are done through the Home Assistant UI.

1. **Wake up the Scale**: Step on the scale briefly to wake up its Bluetooth radio.
2. **Add Integration**:
   - In Home Assistant, go to **Settings** > **Devices & Services**.
   - Home Assistant should automatically discover the "Atflee" device via Bluetooth. Click **Configure**.
   - If it wasn't auto-discovered, click **Add Integration** and search for "Atflee".
3. **Configure User Details**:
   - Setup ends with a first-user step: **Name**, **Height**, **Birth Date**, **Sex** and an optional **Expected weight**.
   - This information is required for the scale to calculate body composition metrics (Fat, Muscle, etc.) locally or via its algorithm.
4. **Finalize**:
   - Once configured, stay on the scale until the measurement is complete and synced to HA.

## Multiple users

Each person is a **User** subentry of the scale (Settings > Devices & Services > Atflee > Add user) with their own device and sensors.

- **Active user** (select on the scale device): `auto` or one of the users. The choice is used when the scale connects and for the next weight, then falls back to `auto` after one finished measurement or after 10 minutes. It is not kept across restarts or reloads. Once the first stable weight of a measurement has been attributed, changing it does not move that measurement (a selection made before the first stable weight does apply).
- **Default user** (integration options): the user assumed in `auto` mode. Leave it empty to use the first user (lowest slot).

### Who is stepping on the scale (auto mode)

With two or more users and the select on `auto`, the first weight of a measurement decides whose it is:

1. Each user's reference weight is their last stable weight (stored by the integration, also across restarts) or, until there is one, the **Expected weight** from their profile. Users with neither are never matched.
2. The user with the nearest reference weight is taken if the difference is within **Weight match tolerance** (integration options, default 3 kg) and that user is at least 1.5 kg closer than the runner-up. Otherwise the match is considered ambiguous.
3. If nobody can be matched, the **default user** is assumed (`assignment: fallback`). But if the weight differs from the default user's reference weight by more than **Fallback max weight difference** (default 15 kg), the measurement is **not recorded for anyone** and the `atflee_unassigned_measurement` event is fired with `address`, `weight`, `timestamp`, `reason` (`no_candidates`, `out_of_tolerance` or `ambiguous`) and the `candidates` considered (`user_id`, `name`, `reference_weight_kg`, `difference_kg`). Use it for a notification or a manual assignment automation.
4. A user picked on the select is always used (`assignment: selected`), and with only one user there is nothing to decide (`assignment: default`).

The decision is made on the first *stable* weight, not on the unstable readings while the weight is still settling; until then, with several users in `auto`, those readings only update the scale diagnostics.

Each stable weight becomes the user's reference weight for next time, except for a `fallback` measurement: that only sets a reference for a user who has none (neither a stored nor an expected weight), so a guest cannot shift the default user's reference.

Every user sensor carries an `assignment` attribute: `matched`, `fallback`, `selected` or `default`. Before the stable weight, readings that go to a selected or single user carry `assignment: null`. User sensors only carry that user's own measurement attributes; the raw last packet and the connection details are on the scale's sensors.

Deleting a user removes their device and entities, and their stored weight is dropped on the next reload of the integration.

The body-composition profile is sent to the scale when it connects, before the weight is known, so it is the one of the selected or default user. If the weight then identifies somebody else, the scale's own body fat value is discarded and body fat, BMI and the other metrics are calculated by the integration for the identified user from the raw impedances.

## How It Works

- The integration listens for Atflee scale advertisements and connects when a measurement is detected.
- It provides real-time updates for weight and body composition.
- Home Assistant creates these entities, each person on their own device.

**Per user (one device per user)**

- **Weight (kg)** and **Impedance (ohm)** always exist.
- Everything else is created the first time that user gets a value, so values the scale never delivers do not show up as permanently unknown entities: **BMI**, **Body Fat (%)**, **Muscle Mass (kg) / Muscle (%)**, **Visceral Fat**, **Subcutaneous Fat (%)**, **BMR (kcal)**, **Bone Mass (kg)**, **Body Water (%)**, **Protein (%)**, **Skeletal Muscle (%)**, **Body Age (years)**, **Body Score**, **Heart Rate (bpm)** (if supported by the model) and the derived masses **Body Fat Mass / Fat-Free Mass / Body Water Mass / Protein Mass / Skeletal Muscle Mass (kg)** (calculated from weight and the body fat / body water / protein / skeletal muscle %).

**Scale device**

- **Battery (%)**
- Diagnostic: **Connection** (binary sensor), **Connection Duration**, **Verify Status**, **Measure Status**, **Scale Status**, **Failure Count**, **Last Failure**
- **Active user** (select) and **Body composition measurement** (switch)

## Device Settings (Configuration)

- Each person is a **user** of the scale. Use **Add user** on the integration entry to add one, or the user's **Reconfigure** action to change their name, height, birth date, sex or expected weight (the expected weight lets the integration recognise a user by weight before a first measurement). These values are used to calculate the body composition metrics correctly.
- **Configure** on the integration entry holds the idle disconnect timeout, the body composition switch, the default user and the weight identification thresholds (match tolerance, fallback max weight difference).

## Upgrading from 0.3.2 or earlier (no migration)

There is no migration. The old entry has no user, and until you add one with **Add user** no weight is recorded at all (with no user, measurements only reach the scale's latest-packet diagnostics, not any weight entity). Height, birth year and sex are not carried over, so enter them again in the new user. The old measurement entities (unique ids `{address}_weight`, `{address}_body_fat`, ...) are no longer provided and should be deleted by hand. Battery and diagnostic entities keep their ids.

## Troubleshooting

- **Connection timed out**: Ensure you are standing on the scale while configuring or syncing. The scale turns off its Bluetooth radio quickly when not in use.
- **Missing body composition data**: BMI and body composition need at least one user with the correct height, birth date and sex. Some models require these to be sent to the device to trigger the body fat measurement.
- **`Connection terminated by peer`**: BLE interference or weak signal. Try moving the device closer to your Home Assistant Bluetooth adapter or use an ESPHome Bluetooth proxy.



