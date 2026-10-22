# BluOS API Notes

Source of truth: [BluOS Custom Integration API v1.7](https://bluesoundprofessional.com/wp-content/uploads/2025/06/BluOS-Custom-Integration-API_v1.7.pdf) (also published at bluos.io). Checked against BluOS firmware 4.18. The PDF is not sufficient on its own.

The BluOS API is device-specific. Each player endpoint responds independently over HTTP — typically port **11000** for primary zones, and **11010+** for CI secondary zones (e.g. NAD CI S2 `_musp` SRV records). There are no broadcast or multi-device endpoints — multi-device control is implemented client-side by iterating over discovered `ip:port` endpoints.

## Endpoints Used

| Category | Endpoints | Notes |
|----------|-----------|-------|
| Playback | `/Play`, `/Pause`, `/Stop`, `/Skip`, `/Back` | Per-device, safe to call concurrently |
| Queue | `/Playlist`, `/Clear`, `/Move?old=&new=` | Play queue (not `/Queue`) |
| Inputs | `/Settings?id=capture&schemaVersion=32`, `/Play?inputTypeIndex=` | Capture list + select (fw ≥ 4.2) |
| Bluetooth | read from capture settings `bluetoothAutoplay`; set `/audiomodes?bluetoothAutoplay=` | No `/AudioModes` GET in v1.7 |
| Presets | `/Presets`, `/Preset?id=` | Per-device presets |
| Sync | `/AddSlave`, `/RemoveSlave`, `/SyncStatus` | Primary controls runtime group |
| Status | `/Status` | Volume, state, track info |
| System | POST `/reboot` on port 80 with `yes=1`, `/diagnostics` on port 80 | The BluOS port has no reboot handler |

### Do not use (legacy / non-spec)

These return **404** on firmware 4.18: `/Queue`, `/AudioInputs`, `/AudioInput`, `/AudioModes`, and `:11000/diagnostics`. Uptime is on port 80 `/diagnostics`, in `<dt>Uptime:</dt><dd>…</dd>`.

Legacy sync query forms (`/Sync?slave=`, `/Sync?remove=`) may still exist on some firmware versions, but current BluOS grouping uses **`AddSlave`** and **`RemoveSlave`** on the primary player.

## Play queue (`/Playlist`)

Song entries use elements `title`, `art` (artist), `alb` (album), `service`, plus attribute `id` (queue position). Prefer `/Playlist?start=0&end=N` for bounded responses.

## Capture inputs

`GET /Settings?id=capture&schemaVersion=32` returns a settings tree. Input sources are `menuGroup` nodes under `capture` (e.g. `capture-input0` = Analog). Bluetooth mode is the `setting` with `id="bluetoothAutoplay"` (`value` 0–3).

Select an input with `GET /Play?inputType=<type>&index=<n>` (firmware 4.18). `GET /Play?inputTypeIndex=<type>-<n>` returns 404 on that firmware and remains as a fallback.

## SyncStatus XML

`GET /SyncStatus` describes both standalone players and runtime sync groups.

### Primary (group leader)

```xml
<SyncStatus group="Zone One+Player A" name="Zone One">
  <slave id="192.168.1.20" port="11000"/>
</SyncStatus>
```

### Slave (group follower)

```xml
<SyncStatus name="Player A">
  <master port="11000">192.168.1.32</master>
</SyncStatus>
```

Values may include a port suffix (`192.168.1.32:11000` or `192.168.1.30:11010`). Clients should preserve the port for API calls and sync membership; bare IPs default to `11000`.

### CI secondary zones

Multi-zone CI players advertise each zone as its own BluOS id (often `ip:11010`, `ip:11011`, …). mDNS service `_musp._tcp` carries the SRV port; `_musc._tcp` is the primary. SyncStatus `<slave id="…" port="…"/>` and `<master port="…">` must be combined into a canonical `ip:port` endpoint.

## Sync Group Behavior

Runtime sync groups are managed through the **primary** device:

- **Create / add slave:** `GET http://<primary-ip>:<primary-port>/AddSlave?slave=<slave-ip>&port=<slave-port>`
- **Remove slave / ungroup:** `GET http://<primary-ip>:<primary-port>/RemoveSlave?slave=<slave-ip>&port=<slave-port>`
- Playback commands on the primary propagate to all slaves automatically
- Ungrouping must be sent to the **primary**, not broadcast to every player endpoint
- If the primary is offline, orphaned secondaries can be re-parented briefly onto a reachable donor, then removed, so they become standalone again

## Implementation Pattern

1. Discover endpoints (mDNS `_musc`/`_musp` and/or LSDP); verify `/SyncStatus` before caching
2. Filter by name pattern if specified
3. Call the API on each matching `ip:port` via `ThreadPoolExecutor`
4. Report per-device success/failure

For sync operations specifically:

1. Query `/SyncStatus` on each player to learn primary/slave relationships (endpoint-aware)
2. Send `AddSlave` / `RemoveSlave` only to the primary endpoint, passing the slave port
3. Use `sync list` to verify group state after changes
