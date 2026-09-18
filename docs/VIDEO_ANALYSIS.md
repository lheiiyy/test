# Video Analysis — Reference Recreation Source

**Source file:** user-provided `.mp4`, analyzed frame-by-frame (ffmpeg extraction at 3 fps, 50 frames, 720×1280 upscaled from a 360×640 source; total runtime 16.6s, H.264/AAC, no dialogue/narration — audio is background music only, not transcribed).

**Method:** The video was screen-recorded vertically on a phone, pointed at a PC monitor with a second Android phone held in frame. No live footage of Claude "watching" a stream — every claim below is anchored to a specific extracted frame, cited inline.

## 0. Important context that changes how this project must be scoped

Before any feature inventory, three things need to be said plainly, because they determine what gets built and what doesn't:

1. **This is not a commercial MDM product.** The on-screen software is a **terminal/CLI script**, not a GUI desktop app. It prints an ASCII-art banner reading **"Phantom-Droid"**, subtitled **"PhantomDroid v2.0"**, credited **"Created by HexSec"** (frame_035, frame_030).
2. **The device shown running the demo is browsing an Instagram account, `@hexsecteam` ("HexSec Team"),** whose bio reads "Learn Ethical Hacking", "Red Teaming & Pentesting", **"Malware Dev | Exploit Dev | OffSec... more"**, and links a Telegram (`telegram.me/hexsecteam_tools`) (frame_020, frame_025). The video ends with an on-screen call-to-action: **"For tool comment 'PhantomDroid'"** (frame_045, frame_048, frame_050) — a lead-generation pattern used to distribute the tool via social media comments/DMs rather than a normal software listing.
3. **No part of the visible menu (items 1–46 of 55) shows anything beyond standard `adb`-level functionality** — device listing, wifi/tcpip connect, app install/uninstall, package info, battery/memory/CPU/storage stats, process/network info, and screen mirroring (backed by `scrcpy`, referenced directly at menu item 44, "Check scrcpy"). **Nothing in the captured frames shows camera/microphone activation, keylogging, SMS/call/contacts access, location tracking, credential harvesting, or persistence/hiding behavior.** Two numeric ranges (19–27 and 47–55, out of the stated 1–55) are **never shown on screen at any point in the video** — the printed menu jumps directly from item 18 to item 28, and from item 46 the transcript ends before 47–55 would print. Their contents are **undetermined**, not confirmed-safe.

**Decision:** Given (1) and (2), this project will **not** reuse the name "Phantom-Droid"/"PhantomDroid", the "Created by HexSec" credit, the ASCII skull/red-terminal branding, or the "comment to get the tool" distribution pattern. The recreation is named **DroidBridge** and is built as a transparent, GUI-first, source-available desktop tool whose only backend is the standard Android Debug Bridge (`adb`) plus `scrcpy` for mirroring — the same legitimate mechanisms a developer would otherwise script by hand. Given (3), every reproduced feature maps to a confirmed, legitimate `adb`/`scrcpy` capability; the two undetermined ranges are **not implemented**, on the grounds that we cannot verify what they do and therefore cannot verify they're safe to copy. This is intentional and is the "replace unsafe/unauthorized operations with an explicit, authorized equivalent" instruction being applied at the category level, not just per-button.

---

## 1. Frame-by-frame walkthrough

| Frame(s) | Timestamp (approx) | What's on screen |
|---|---|---|
| frame_001–004 | 0.0–1.3s | PC monitor, dark terminal with red ASCII "Phantom-Droid" banner top-left. A browser tab "Remote Android Screen QR" is open at `http://192.168.1.11:XXXX` (marked "Not secure" — plain HTTP). A phone in the foreground shows the Instagram profile `@hexsecteam`. |
| frame_005–009 | 1.3–3.0s | Phone pulls up its quick-settings/lock screen ("Emergency calls only") — establishing this is a *second*, separate Android phone (the one being managed), not the one filming. |
| frame_010–014 | 3.0–4.6s | Phone's camera/QR scanner opens, framing the PC browser's QR code ("Find a QR code" / "Scan"). Terminal menu is now readable: DEVICE MANAGEMENT / APP MANAGEMENT columns, then SYSTEM MONITORING / SCREEN SHARING columns below, prompt `Enter your choice (1-55, 99 to exit):`. |
| frame_015–019 | 4.6–6.3s | Full browser pairing page visible: **"Scan the QR to open Remote Android Screen" / "Open this page on your PC and scan from the connected phone" / [QR code] / "Or open the link manually — Click here."** |
| frame_020–024 | 6.3–8.0s | Phone returns to the Instagram profile (used here just as a hand/camera anchor, not part of the app flow). |
| frame_025–029 | 8.0–9.6s | Terminal shows a connection result: `[NEW SESSION]` / `Device: 192.168.1.6:5555` / `IP: 192.168.1.6` / `Status: READY` / `Time: 2026-08-30 19:40:07`. Port 5555 is the standard `adb tcpip` wireless-debugging port — confirms pairing = `adb connect <ip>:5555` after Wi-Fi debugging is enabled on the phone. |
| frame_030–034 | 9.6–11.3s | Full, clean menu text (this is the sharpest frame — see transcription in §2 below). |
| frame_035–039 | 11.3–13.0s | User types `37` (Start screen sharing). Output: `Registered READY sessions: 1. 192.168.1.6:5555 (192.168.1.6) [READY] / 0. Select device manually` → user selects `1` → `Screen sharing started for 192.168.1.6:5555` → `Press Enter to continue...` |
| frame_040–044 | 13.0–14.6s | A new desktop window titled **"Remote Android Screen"** opens, live-mirroring the managed phone's actual screen content (the same Instagram profile is visible inside this mirrored window, matching the physical phone next to it in real time). |
| frame_045–050 | 14.6–16.6s | Mirror window continues updating (scrolling the Instagram grid). Overlay text appears: **"For tool comment 'PhantomDroid'"** — end card / call to action. |

## 2. Full on-screen menu transcription (frame_030, highest legibility)

```
Phantom-Droid                                    PhantomDroid v2.0
                                                   Created by HexSec
------------------------------------------------------------------
DEVICE MANAGEMENT          |  APP MANAGEMENT
 1. List devices           |  10. Install APK
 2. Connect WiFi           |  11. Uninstall app
 3. Disconnect device      |  12. List packages
 4. Device Info            |  13. Package info
 5. Restart PhantomDroid   |  14. Clear app data
 6. Check connection       |  15. Force stop app
 7. Execute shell command  |  16. Start app
 8. Get device logs        |  17. Backup app
 9. Reboot device          |  18. Batch install
SYSTEM MONITORING          |  SCREEN SHARING
28. Battery info           |  37. Start screen sharing
29. Memory info            |  38. Generate QR Payload(?)
30. CPU info               |  39. Custom screen sharing
31. Storage info           |  40. Stop screen sharing
32. Running processes      |  41. Stop all sharing
33. Network info           |  42. Show active sessions
34. System properties      |  43. Multi-device sharing
35. Apps with size         |  44. Check scrcpy
36. Monitor performance    |  45. Record screen
                           |  46. Sync folder

Enter your choice (1-55, 99 to exit):
```

Note the **numbering gap**: 19–27 (a 9-item category between "APP MANAGEMENT" and "SYSTEM MONITORING") and 47–55 (a 9-item category after "SCREEN SHARING") are declared by the "1-55" range in the prompt but **never printed on screen in any frame of this video**. This is the single largest unknown in the source material. Given the categories present (device mgmt, app mgmt, system monitoring, screen sharing), a plausible missing category is "FILE MANAGEMENT" or "NETWORK TOOLS" for 19–27, and something like "UTILITIES/ADVANCED" for 47-55 — but this is a guess, explicitly logged as such, and **nothing was implemented from it.**

## 3. Confirmed vs. inferred vs. undetermined

**Confirmed by direct frame evidence:**
- CLI, not GUI; text menu with numbered categories; a "1-55, 99 to exit" input loop.
- Wireless ADB pairing via QR code → opens a locally-hosted HTTP page → phone scans with its native camera/QR reader → underlying transport is `adb connect <lan-ip>:5555`.
- A connection-state readout (`[NEW SESSION]`, device address, status, timestamp).
- A "screen sharing" feature that lists ready sessions, lets the operator pick one, and opens a separate live-mirrored window of the target device's actual screen.
- Menu item text for categories DEVICE MANAGEMENT (1–9), APP MANAGEMENT (10–18), SYSTEM MONITORING (28–36), SCREEN SHARING (37–46).
- Branding, credit line, and the social-media distribution call-to-action described in §0.

**Inferred (reasonable, not directly shown executing on screen):**
- Each menu item's behavior, inferred from its label only (e.g. "7. Execute shell command" almost certainly opens a prompt that runs the typed command via `adb shell`; "28. Battery info" almost certainly runs `adb shell dumpsys battery`). None of items 1–36 or 38–46 are shown being selected/executed in this clip except #37.
- The mirroring window is most likely `scrcpy` output re-hosted in a window (menu item 44, "Check scrcpy", strongly implies scrcpy is a runtime dependency) rather than a from-scratch protocol.
- The QR pairing page is likely served by a small local web server (Flask/Node) bundled with the script, given the plain "Not secure" HTTP address and generic page chrome.

**Cannot be determined from the video:**
- The full contents of menu ranges 19–27 and 47–55 (18 items total, ~33% of the stated feature count).
- What language/runtime the original script is written in (Python is a reasonable guess from the banner/menu style, but not confirmed).
- Whether the pairing QR flow performs any authentication/authorization step beyond "same LAN, scan code" (no permission-grant screen, consent dialog, or credential prompt appears in any frame).
- Exact visuals of "Generate QR Payload" (#38) — the name alone is ambiguous and, out of caution, is **not** reproduced as named (see Known Limitations in FEATURE_SPEC.md).

## 4. Screens identified (used as the basis for UI_SPEC.md)

1. Banner / idle terminal (no device connected)
2. Main categorized menu + input prompt
3. QR pairing web page (served locally)
4. Connection-result readout
5. Screen-sharing session picker
6. Live remote-screen mirror window
7. (Inferred only) Per-command output screens for each of the ~28 confirmed-legitimate menu actions — never individually shown except screen sharing, so their *content* in our app is designed from what the command legitimately returns, not from a captured screenshot.

See `docs/UI_SPEC.md` for the per-screen spec and `docs/FEATURE_SPEC.md` for the feature-by-feature reproduce/adapt/omit decision.
