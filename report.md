# Workflow Report — PicoQuant snAPI Fast Counter for qudi

**Scope:** integrate a PicoQuant TCSPC / event-timer device into the local qudi installation as a
`FastCounterInterface` module, per the task brief `multiharp_qudi_integration_brief.md`.
**Status:** implementation complete and verified without hardware. Not yet run against a physical
device — the PicoQuant device driver is not installed on this machine.

---

## 1. Starting state

| Item | Finding |
|---|---|
| qudi | `qudi-core` 1.6.1.dev0 + `qudi-iqo-modules` 0.6.0.dev0, editable installs under `qudi-env\Scripts\` |
| Python | 3.14.3, 64-bit, PySide6 6.10.2 |
| PicoQuant software | **Not installed.** No `mhlib*.dll` / `hhlib64.dll` anywhere, no `C:\Program Files\PicoQuant`, no `mhdefin.h` / `mhlib.h` |
| snAPI | Not installed at the start |
| User config dir | `C:\Users\pengw\qudi\config\` |

### The PicoQuant-provided file

`snapi_fast_counter.py`, sitting loose in the repo root, turned out to be **already a complete
`FastCounterInterface` implementation** — not a raw DLL demo and not C headers. Key properties:

- Built on **snAPI**, not raw `MHLib`.
- Docstring targets a HydraHarp 500, but snAPI itself is device-generic.
- **Gated-only**: `is_gated()` hardcoded `True`, `configure()` rejects `number_of_gates = 0`.
- Not in the qudi module tree, so it could not be referenced from a config.

### The suggested template

`src/qudi/hardware/picoquant/hydraharp400.py` was named in the brief as the closest template. Its
**gated path is an unimplemented `pass` / TODO** (lines 286–288), so it is not a usable model for
the spin-coherence half of the job.

---

## 2. Decision: snAPI rather than a hand-ported MHLib wrapper

The brief allowed either path (§4.5). snAPI was chosen because:

1. PicoQuant supplied snAPI code, so it is the vendor's own recommended integration route here.
2. A `HH_*` → `MH_*` port could not be verified on this machine — no headers, no DLL, no library
   manual. Guessing at C signatures produces code that compiles and then misbehaves silently.
3. snAPI covers MultiHarp 150/160, HydraHarp 400/500, PicoHarp 330 and TimeHarp 260 through one
   API, so the module does not hard-code a model. The device is detected and logged at activation.
4. The vendor file already solved the hard part: unfolding the T2 timetag stream into gates.

Confirmed after installation: **snAPI ships the harp libraries itself** — `mhlib64.dll`,
`hhlib64.dll`, `HH500Lib.dll`, `PH330Lib.dll`, `th260lib64.dll`. This answers the brief's open
question §7 about which DLL is present on the machine.

---

## 3. Implementation

Module: [`src/qudi/hardware/picoquant/snapi_fast_counter.py`](src/qudi/hardware/picoquant/snapi_fast_counter.py)

### 3.1 Ungated mode added

The brief needs both operating modes; the vendor file only did gated. Both are now one code path:
photons are histogrammed against the most recent preceding trigger, and triggers are assigned
cyclically to *N* histogram rows.

- `N = number_of_gates` → 2D `[gate_index, timebin]` for Rabi / Ramsey / Hahn echo / CPMG.
- `N = 1` → the summed arrival-time histogram, returned as **1D**, for lifetime / decay.

`gated` is a `ConfigOption` rather than being inferred from `configure()`, because
`PulsedMeasurementLogic` calls `is_gated()` *before* `configure()`
(`src/qudi/logic/pulsed/pulsed_measurement_logic.py:286`).

### 3.2 Structure

The binning was extracted into `_GateAccumulator`, a pure-numpy class holding **no snAPI and no
qudi state**. This is what makes the logic testable without hardware, and it keeps the qudi module
responsible only for device lifecycle, threading and status.

### 3.3 Robustness changes over the vendor file

| Change | Reason |
|---|---|
| Deferred snAPI import | The module file imports (and its logic is testable) without snAPI. Activation raises a clear install message instead of an opaque config-load `ImportError`. |
| `elapsed_sweeps` per mode | Trigger count when ungated, `triggers // gates` when gated. The vendor file only handled the gated case. |
| `min_binwidth_s` (default 1 ns) | Trims the advertised bin-width list. Without it the pulsed logic falls back to `hardware_binwidth_list[0]` = the 5 ps base resolution (`pulsed_measurement_logic.py:280-281`), which at 100 gates × 3 µs allocates ~480 MB. |
| `max_histogram_mib` (default 512) | Turns an accidental over-allocation into a readable `ValueError` instead of a `MemoryError`. |
| Single-instance guard | snAPI wraps a process-global C API; a second live instance **aborts the process**. The module now raises instead. |
| `ptu_file` option | Hardware-free replay — see §5. |

### 3.4 Verified against the snAPI source

Every assumption inherited from the vendor file was checked against the installed
`snAPI/Main.py` rather than trusted:

- `unfold.getBlock()` returns a `c_uint64` times buffer and a `c_uint8` channels buffer — so the
  module's `np.uint64` / `np.uint8` casts are exact, not truncating.
- Marker flag is `(0x80 & channel) != 0`; marker bits are `0x7F & channel`, bit 0..3 for markers
  1..4. Matches the module's masking.
- snAPI channel numbering is 0 = sync, 1..N = inputs; PTU record channel *n* maps to snAPI *n+1*.
- **In `MeasMode.T3` the sync records are stripped from the unfold stream.** This is why the module
  uses T2 for both modes: without sync events there is no trigger to bin against.

---

## 4. Config wiring

`C:\Users\pengw\qudi\config\picoquant_pulsed.cfg`
— pulsed GUI → master logic → measurement logic → the fast counter, with `pulser_dummy` so it
starts without a real pulse generator. Parses cleanly with `qudi.util.yaml`.

`fast_counter_dummy` is kept in the same file so the two can be swapped on one line, which is the
cross-check the brief asks for in §6.

---

## 5. Hardware-free testing

**Question:** can this be tested without the device?
**Answer: yes.** snAPI has no simulation or demo mode, but `snAPI.getFileDevice(path)` opens a PTU
file and — in PicoQuant's own words — handles it "like a real device". `initDevice` is skipped and
every measurement class works on it.

The exact code path the module uses was verified to stream off a file:
`unfold.startBlock` → `getBlock` → `isFinished` → `stopMeasure`.

### 5.1 Synthetic PTU generator

[`tests/synthetic_ptu.py`](tests/synthetic_ptu.py) writes Generic-T2 PTU files with a chosen
trigger/photon pattern. The record layout was taken from PicoQuant's own reference reader
(`PicoQuant-Time-Tagged-File-Format-Demos`, `PTU/Python/Read_PTU.py`), not guessed:

- 32-bit little-endian record: 1 bit `special`, 6 bit `channel`, 25 bit `timetag`.
- `special=1, channel=0` → sync; `channel=1..15` → markers; `channel=0x3F` → overflow.
- `special=0` → photon on input `channel`, which snAPI reports as `channel + 1`.
- The 25-bit field wraps every 33 554 432 ticks, so overflow records are emitted automatically.

Runnable as a script: `python tests/synthetic_ptu.py <output.ptu>`.

Header tags were iterated against snAPI empirically. Two corrections were needed: base resolution
is stored in the header in **seconds** (snAPI reports it in ps), and `Measurement_Mode` must be 2
for T2.

### 5.2 The `ptu_file` config option

Setting `ptu_file` makes the module open a file device instead of a harp and run its normal
acquisition path against the replayed stream. A ready-made file is provided:
`C:\Users\pengw\qudi\config\dryrun_multiharp_t2.ptu` — 2000 sweeps of an exponential decay,
τ = 800 ps, sync on channel 0, photons on channel 1. It is referenced (commented out) in the config.

---

## 6. Tests

| File | Tests | Needs |
|---|---|---|
| [`tests/test_snapi_fast_counter.py`](tests/test_snapi_fast_counter.py) | 15 | numpy only — no snAPI, no hardware, no qudi instance |
| [`tests/test_snapi_fast_counter_ptu.py`](tests/test_snapi_fast_counter_ptu.py) | 6 | snAPI — no hardware |

Run with:

```
pytest tests/test_snapi_fast_counter.py tests/test_snapi_fast_counter_ptu.py --noconftest
```

`--noconftest` is required because the repo's `tests/conftest.py` imports PySide2 while this
environment has PySide6.

**Result: 21 passed**, stable across repeated runs.

Unit tests cover cyclic gate assignment, 1D ungated summing, photons before the first trigger and
past the record length being discarded, the trigger reference carrying across block boundaries,
pause/continue semantics, and marker-vs-channel trigger splitting.

The PTU tests drive **real snAPI → real module code**: gated peaks land in the correct rows, the
ungated histogram matches the written delays bin-for-bin and recovers the generating lifetime,
marker-triggered replay equals sync-triggered replay, timetag overflows survive, and
`configure(…, N)` → `get_data_trace()` returns exactly `(N, record_length/binwidth)` `int64` against
the device description snAPI reports for the file.

A real qudi module cannot be instantiated outside a running qudi application, so the tests call the
production methods against a small stub carrying only the attributes those methods touch. The code
under test is the production code, unmodified.

---

## 7. snAPI constraints discovered

Each of these **aborts the interpreter** rather than raising, so they are worth recording:

1. **A second live `snAPI()` instance in one process.** The module guards against this and raises a
   readable error instead of taking qudi down.
2. **`closeDevice()` called between two `getFileDevice()` calls.** Reopening files on one instance
   is fine; closing in between is not. Confirmed by a 15-cycle stress test: without `closeDevice`
   it survives, with it the process dies.
3. **The DLL's console logging against pytest's fd-level capture.** Fixed in the test fixture by
   disabling console logging through a private `system.ini`.

The realistic qudi lifecycle — activate → measure → deactivate → reactivate — was separately
verified over five cycles and is **safe**, because deactivation drops the snAPI reference and tears
the API down fully. Toggling the module in the qudi GUI will not crash the application.

---

## 8. Environment changes made

| Package | Version | Why |
|---|---|---|
| `snAPI` | 1.2.5 | The device API. Built a `cp314` wheel from source against Python 3.14.3. |
| `pytest` | 9.1.1 | Declared `dev-test` extra of this repo (`pyproject.toml:82`); nothing in `tests/` runs without it. |

Still required for real acquisition: the **PicoQuant device driver / software** for the specific
harp, from picoquant.com/downloads.

---

## 9. Deliverables

| Path | What |
|---|---|
| [`src/qudi/hardware/picoquant/snapi_fast_counter.py`](src/qudi/hardware/picoquant/snapi_fast_counter.py) | The qudi hardware module |
| [`tests/synthetic_ptu.py`](tests/synthetic_ptu.py) | Generic-T2 PTU writer / dry-run file generator |
| [`tests/test_snapi_fast_counter.py`](tests/test_snapi_fast_counter.py) | Hardware-free unit tests |
| [`tests/test_snapi_fast_counter_ptu.py`](tests/test_snapi_fast_counter_ptu.py) | End-to-end tests via PTU replay |
| `C:\Users\pengw\qudi\config\picoquant_pulsed.cfg` | Loadable pulsed-measurement config |
| `C:\Users\pengw\qudi\config\dryrun_multiharp_t2.ptu` | Ready-made dry-run data |

The original vendor file `snapi_fast_counter.py` in the repo root was left untouched as a reference.

---

## 10. Open items

**Needs the hardware present:**

- Install the PicoQuant device driver, then confirm the device is visible in the PicoQuant software
  before pointing qudi at it.
- Export an `.ini` device configuration (trigger/CFD levels, edges, offsets, sync divider) from the
  PicoQuant software and set `ini_config`. The module deliberately does not duplicate those
  front-end settings as qudi options.
- **Trigger source (brief §7).** `trigger_channel: 0` (sync) is the default. Whether the pulser's
  sequence trigger arrives on sync or on a SubD marker input is a wiring fact that cannot be read
  from code — switch to `trigger_marker: 1..4` if it is on a marker.
- Sanity-check total counts against a direct MultiHarp software / SymPhoTime / QuCoa acquisition.

**Not yet done:**

- Loading the config in a live qudi session. The code path is proven by the PTU tests, but the GUI
  has not been launched.

**Known limitation, by design:**

The module runs **T2 for both modes**. For gated spin measurements this is correct. For lifetime
measurements with a high-repetition-rate laser (e.g. 80 MHz), T2 records every sync event, which is
a heavy data rate — T3, or snAPI's hardware `Histogram` class, is the better backend there. That is
the natural next extension and slots in behind the same interface without any config change.
