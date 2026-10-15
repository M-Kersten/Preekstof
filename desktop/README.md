# Preekstof as a desktop app

`Preekstof.app` for a Mac with an Apple chip, and `Preekstof-Setup.exe` for Windows (x64).
Double-click, and Preekstof opens in a window of its own. Nothing else has to be on the
computer: no Python, no Node.js, no FFmpeg, no terminal.

It is the same app as the browser version. `desktop/app.py` starts the FastAPI backend on
`127.0.0.1` and opens a native web view on it with [pywebview](https://pywebview.flowrl.com/)
(WKWebView on a Mac, WebView2 on Windows). PyInstaller packs that file, the backend, the
built interface, Python with every package, and FFmpeg into one folder. Nothing about the
other ways of running Preekstof changes:

| How                                   | For whom                                   |
|---------------------------------------|--------------------------------------------|
| `Preekstof.dmg`, `Preekstof-Setup.exe` | churches: install and double-click         |
| `Preekstof-Mac.zip`, `Preekstof-Windows.zip` | the downloads with Python inside, started with start.command / start.bat |
| `python launcher.py`                  | a checkout, opens the browser              |
| `npm run dev` + `uvicorn --reload`    | working on the code                         |

## Installing

**Mac (Apple chip, macOS 14 or newer).** Open `Preekstof.dmg` and drag Preekstof to
Programma's (Applications). The first time, macOS stops it, because the app is not
notarised by Apple: click **Gereed**, open **Systeeminstellingen → Privacy en beveiliging**,
scroll down and click **Open toch** next to Preekstof, and confirm. After that it opens
like any other app. On macOS 14 the shorter way works too: Control-click the app, choose
**Open**, then **Open** again.

**Windows 10 or 11 (64-bit).** Run `Preekstof-Setup.exe`. SmartScreen does not know the
installer yet: **Meer info → Toch uitvoeren**, once. It installs for this user only, in
`%LOCALAPPDATA%\Programs\Preekstof`, without asking for an administrator password, and puts
Preekstof in the Start menu. Uninstall through Settings → Apps, as usual.

Updating is installing the new version over the old one. The readiness panel in the app
says when there is one and links to it; it does not unpack anything into the app itself.

## Where things are

The church's own work is where it always was, and neither installing nor uninstalling
touches it:

- `~/Preekstof` (`C:\Users\<naam>\Preekstof`): projects, services, settings and API key
  (`config.env`), logs, the church's brand, logos and music, and the person model
  (`vision/person.onnx`, fetched on first use; NOTICE says why it is never in a download).
- The speech models: the Hugging Face cache in the user's home folder, fetched once.
- The window's own storage (what the interface remembers): `~/Preekstof/.venster`.

After the first start and the first service, everything works offline apart from what
needs the internet by its nature: finding moments with Claude (or nothing, with
`LLM_PROVIDER=ollama`), fetching a recording from a link, and the check for a new version.
The smoke test below passes with the network cut off.

## Building

On the computer you build for: a Mac builds the Mac app, Windows the Windows one. There is
no cross-building with PyInstaller.

```bash
# Mac, Apple chip. Python 3.12 and the command line tools (xcode-select --install).
bash desktop/build-mac.sh
```

```powershell
# Windows x64. Python 3.12 (py launcher) and, for the installer, Inno Setup 6
# (winget install JRSoftware.InnoSetup).
powershell -ExecutionPolicy Bypass -File desktop\build-windows.ps1
```

Both make a virtual environment in `desktop/.venv`, install `backend/requirements.txt` and
`desktop/requirements.txt`, take PyAV out again, and run `desktop/build.py`, which:

1. fetches FFmpeg for this computer into `desktop/build/ffmpeg`, from the same builders the
   launcher uses (gyan.dev for Windows, martin-riedl.de for the Mac), refuses one without
   libass, and writes its licence and version beside it;
2. runs PyInstaller with `desktop/preekstof.spec`;
3. fails if the real PyAV came along (see below), and on a Mac if anything inside needs a
   newer macOS than the app says it does;
4. starts the packed app with `--smoke`: the page and fonts are served, a clip with
   subtitles is made through the bundled FFmpeg, the speaker is followed, a sentence is
   written out with the tiny model (75 MB, downloaded once), the modules nobody exercised
   are imported, and a real window has to show the interface;
5. packs `desktop/out/Preekstof.dmg` (Mac) or `desktop/out/Preekstof-Setup.exe` (Windows).

`--no-window` tests without opening a window, `--skip-check` skips step 4. On Linux the
same script packs a folder to try PyInstaller with, without a window or a package.

The release workflow (`.github/workflows/release.yml`, jobs `app-mac` and `app-windows`)
does all of this on GitHub's Mac (Apple chip) and Windows runners, then opens the Mac app
out of its disk image with the quarantine flag on FFmpeg, and installs, starts and
uninstalls the Windows one. `Preekstof.dmg` and `Preekstof-Setup.exe` go into the release
next to the zips, under names that never change, so
`https://github.com/M-Kersten/Preekstof/releases/latest/download/Preekstof.dmg` always
gives the newest.

## Why it is put together like this

- **One folder, not one file.** A one-file `.exe` unpacks some 400 MB into a temporary
  folder at every start.
- **The port stays the same** (8765, or the next free one up to 8784; `PREEKSTOF_PORT`
  sets it). The interface keeps its settings in the browser storage of its address, and a
  new port each run would forget them.
- **One app at a time.** `~/Preekstof/.desktop.json` says which port is in use; a second
  double-click shows that Preekstof is already open, instead of a second server on the same
  folder.
- **Closing the window stops the work** that was running, and the FFmpeg it started. A
  service that was being written out continues where it was the next time.
- **No console windows on Windows** for every FFmpeg the app starts.
- **Windows without WebView2** (rare on Windows 10, never on 11): the app opens in the
  browser instead, and a message box keeps it running until OK is clicked.
- **PyAV is left out.** faster-whisper imports it but only uses it to open audio files
  itself, which Preekstof never lets it do. `desktop/stubs/av` stands in for it, because
  the real wheel carries an FFmpeg built with x264 and x265 (GPL) that would be loaded into
  the app's own process. The FFmpeg the app does carry is a separate program.
- **No paid Apple or Microsoft certificates.** PyInstaller signs the Mac app ad hoc, which
  Apple Silicon requires to run at all; without notarisation macOS asks once, as described
  above. Windows shows SmartScreen once. Both go away only with a paid certificate.

## What the runners cannot tell

- The first-launch dialogs themselves (Gatekeeper's "Open toch", SmartScreen's "Toch
  uitvoeren"): they need a person at a screen.
- Dragging a file from Finder or Explorer onto the window, and the save dialog of a
  download, inside the web view. Choosing a file with the button works the same as in a
  browser.
- An Intel Mac: the desktop app is for the Apple chip only. Intel Macs keep
  `Preekstof-Mac-Intel.zip`.
