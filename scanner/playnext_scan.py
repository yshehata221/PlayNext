#!/usr/bin/env python3
"""
PlayNext local library scanner.

Does what the NVIDIA / Xbox apps do: looks at every launcher installed on this
machine and works out which games are on disk. No dependencies beyond the
Python standard library, so it can be run as-is or packaged into a single .exe
with PyInstaller (see scanner/README.md).

    python playnext_scan.py                 # print what it found
    python playnext_scan.py --json          # machine-readable
    python playnext_scan.py --push          # send to your PlayNext account

Detection per launcher (Windows unless noted):
  Steam       libraryfolders.vdf -> appmanifest_*.acf in each library   (also macOS/Linux)
  Epic        %ProgramData%\\Epic\\EpicGamesLauncher\\Data\\Manifests\\*.item
  GOG         registry HKLM\\SOFTWARE\\WOW6432Node\\GOG.com\\Games
  Ubisoft     registry HKLM\\SOFTWARE\\WOW6432Node\\Ubisoft\\Launcher\\Installs
  EA          registry HKLM\\SOFTWARE\\Electronic Arts / EA Games (install dirs)
  Battle.net  %ProgramData%\\Battle.net\\Agent\\product.db (binary, we grep it)
  Xbox        Appx packages whose install folder contains MicrosoftGame.config
"""
from __future__ import annotations

import argparse
import base64
import getpass
import glob
import json
import os
import platform
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass

IS_WIN = platform.system() == "Windows"
IS_MAC = platform.system() == "Darwin"


@dataclass
class Found:
    title: str
    platform: str            # steam, epic, gog, ubisoft, ea, battlenet, xbox
    steam_appid: int | None = None
    install_path: str | None = None
    cover_data: str | None = None   # base64 image pulled from the launcher's own files
    cover_mime: str | None = None
    store_id: str | None = None     # Microsoft Store product id, so the server can fetch the real poster


# --------------------------------------------------------------------- Steam
# Valve's KeyValues text format. This handles the subset the manifests use.
def parse_vdf(text: str) -> dict:
    tokens = re.findall(r'"((?:\\.|[^"\\])*)"|(\{)|(\})', text)
    stack: list[dict] = [{}]
    key: str | None = None
    for s, open_, close in tokens:
        if open_:
            new: dict = {}
            stack[-1][key] = new
            stack.append(new)
            key = None
        elif close:
            stack.pop()
        elif key is None:
            key = s
        else:
            stack[-1][key] = s
            key = None
    return stack[0]


# software that lives in Steam but isn't a game
STEAM_NOT_GAMES = {431960, 228980, 1070560, 1391110, 1826330}  # Wallpaper Engine, Steamworks Common, Steam Linux Runtime, Proton


def steam_root() -> str | None:
    candidates = []
    if IS_WIN:
        try:
            import winreg
            for hive, path in ((winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam"), (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam")):
                with winreg.OpenKey(hive, path) as k:
                    candidates.append(winreg.QueryValueEx(k, "SteamPath" if hive == winreg.HKEY_CURRENT_USER else "InstallPath")[0])
        except OSError:
            pass
        candidates += [r"C:\Program Files (x86)\Steam", r"C:\Program Files\Steam"]
    elif IS_MAC:
        candidates.append(os.path.expanduser("~/Library/Application Support/Steam"))
    else:
        candidates += [os.path.expanduser(p) for p in ("~/.steam/steam", "~/.local/share/Steam", "~/.var/app/com.valvesoftware.Steam/.local/share/Steam")]
    return next((c for c in candidates if c and os.path.isdir(c)), None)


def scan_steam() -> list[Found]:
    root = steam_root()
    if not root:
        return []
    # libraryfolders.vdf lists the main folder too, with different slashes/case
    # than the registry gives us, so normalise before deduping
    def canon(p: str) -> str:
        return os.path.normcase(os.path.normpath(p))

    libraries = {canon(root)}
    vdf = os.path.join(root, "steamapps", "libraryfolders.vdf")
    if os.path.exists(vdf):
        data = parse_vdf(open(vdf, encoding="utf-8", errors="ignore").read())
        for entry in data.get("libraryfolders", {}).values():
            path = entry.get("path") if isinstance(entry, dict) else entry
            if path:
                libraries.add(canon(path.replace("\\\\", "\\")))

    out: dict[int, Found] = {}  # keyed by appid as a second line of defence
    for lib in libraries:
        for manifest in glob.glob(os.path.join(lib, "steamapps", "appmanifest_*.acf")):
            app = parse_vdf(open(manifest, encoding="utf-8", errors="ignore").read()).get("AppState", {})
            name, appid = app.get("name"), app.get("appid")
            if not name or not appid or int(appid) in out:
                continue
            if "Redistributable" in name or name.startswith("Steamworks") or int(appid) in STEAM_NOT_GAMES:
                continue
            out[int(appid)] = Found(name, "steam", int(appid), os.path.join(lib, "steamapps", "common", app.get("installdir", "")))
    return list(out.values())


# ---------------------------------------------------------------------- Epic
def scan_epic() -> list[Found]:
    if not IS_WIN:
        return []
    folder = os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"), "Epic", "EpicGamesLauncher", "Data", "Manifests")
    out = []
    for item in glob.glob(os.path.join(folder, "*.item")):
        try:
            m = json.load(open(item, encoding="utf-8"))
        except (OSError, ValueError):
            continue
        # DLC and add-ons share the manifest folder; games have a MainGameAppName equal to their own AppName
        if m.get("AppName") != m.get("MainGameAppName"):
            continue
        if m.get("DisplayName"):
            out.append(Found(m["DisplayName"], "epic", None, m.get("InstallLocation")))
    return out


# ------------------------------------------------------------- registry helpers
def _reg_subkeys(hive, path):
    import winreg
    try:
        with winreg.OpenKey(hive, path) as k:
            i = 0
            while True:
                try:
                    yield winreg.EnumKey(k, i)
                    i += 1
                except OSError:
                    break
    except OSError:
        return


def _reg_value(hive, path, name):
    import winreg
    try:
        with winreg.OpenKey(hive, path) as k:
            return winreg.QueryValueEx(k, name)[0]
    except OSError:
        return None


# ----------------------------------------------------------------------- GOG
def scan_gog() -> list[Found]:
    if not IS_WIN:
        return []
    import winreg
    base = r"SOFTWARE\WOW6432Node\GOG.com\Games"
    out = []
    for gid in _reg_subkeys(winreg.HKEY_LOCAL_MACHINE, base):
        name = _reg_value(winreg.HKEY_LOCAL_MACHINE, f"{base}\\{gid}", "gameName")
        if name and _reg_value(winreg.HKEY_LOCAL_MACHINE, f"{base}\\{gid}", "dependsOn") in (None, ""):
            out.append(Found(name, "gog", None, _reg_value(winreg.HKEY_LOCAL_MACHINE, f"{base}\\{gid}", "path")))
    return out


# ------------------------------------------------------------------- Ubisoft
def scan_ubisoft() -> list[Found]:
    if not IS_WIN:
        return []
    import winreg
    base = r"SOFTWARE\WOW6432Node\Ubisoft\Launcher\Installs"
    out = []
    for gid in _reg_subkeys(winreg.HKEY_LOCAL_MACHINE, base):
        path = _reg_value(winreg.HKEY_LOCAL_MACHINE, f"{base}\\{gid}", "InstallDir")
        if path and os.path.isdir(path):
            # Ubisoft doesn't store a display name here; the folder name is the best we get
            out.append(Found(os.path.basename(path.rstrip("/\\")), "ubisoft", None, path))
    return out


# ------------------------------------------------------------------------ EA
def _ea_title_from_installerdata(path: str) -> str | None:
    """Every EA/Origin game folder has __Installer/installerdata.xml with its proper name."""
    try:
        text = open(path, encoding="utf-8", errors="ignore").read()
    except OSError:
        return None
    m = re.search(r'<gameTitle[^>]*locale="en_US"[^>]*>([^<]+)</gameTitle>', text) or re.search(r"<gameTitle[^>]*>([^<]+)</gameTitle>", text)
    return m.group(1).strip() if m else None


def scan_ea() -> list[Found]:
    """
    The EA app (ex-Origin) is inconsistent about where it records installs, so
    look in three places and dedupe by title:
      1. registry keys under EA Games / Electronic Arts / Origin Games
      2. the EA app's own install records in ProgramData/EA Desktop/InstallData
      3. game folders under the usual install roots, identified by installerdata.xml
    """
    if not IS_WIN:
        return []
    import winreg
    out: dict[str, Found] = {}

    def add(title: str | None, path: str | None):
        if title and title.lower() not in out and title not in ("EA Desktop", "EA Core", "EADM", "Origin"):
            out[title.lower()] = Found(title, "ea", None, path)

    # 1. registry
    for base in (r"SOFTWARE\WOW6432Node\EA Games", r"SOFTWARE\WOW6432Node\Electronic Arts",
                 r"SOFTWARE\WOW6432Node\Origin Games", r"SOFTWARE\EA Games", r"SOFTWARE\Electronic Arts"):
        for name in _reg_subkeys(winreg.HKEY_LOCAL_MACHINE, base):
            key = f"{base}\\{name}"
            path = _reg_value(winreg.HKEY_LOCAL_MACHINE, key, "Install Dir") or _reg_value(winreg.HKEY_LOCAL_MACHINE, key, "InstallDir")
            if path and os.path.isdir(path):
                title = _reg_value(winreg.HKEY_LOCAL_MACHINE, key, "DisplayName")
                title = title or _ea_title_from_installerdata(os.path.join(path, "__Installer", "installerdata.xml")) or name
                add(title, path)

    # 2. EA app install records
    program_data = os.environ.get("ProgramData", r"C:\ProgramData")
    for xml in glob.glob(os.path.join(program_data, "EA Desktop", "InstallData", "*", "*", "__Installer", "installerdata.xml")):
        add(_ea_title_from_installerdata(xml), os.path.dirname(os.path.dirname(xml)))

    # 3. game folders under the usual roots (and any custom root the EA app recorded)
    roots = [r"C:\Program Files\EA Games", r"C:\Program Files (x86)\Origin Games", r"C:\Program Files (x86)\EA Games"]
    custom = _reg_value(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Electronic Arts\EA Desktop", "InstallPath")
    for drive in "CDEFG":
        roots += [f"{drive}:\\EA Games", f"{drive}:\\Games\\EA Games", f"{drive}:\\Origin Games"]
    if custom:
        roots.append(custom)
    for root in roots:
        for xml in glob.glob(os.path.join(root, "*", "__Installer", "installerdata.xml")):
            add(_ea_title_from_installerdata(xml) or os.path.basename(os.path.dirname(os.path.dirname(xml))), os.path.dirname(os.path.dirname(xml)))

    return list(out.values())


# ------------------------------------------------------------------ Battle.net
# Battle.net's own records are a protobuf blob, so we use three sources:
#   1. Battle.net.config (JSON) lists the product codes you have installed
#   2. product.db contains the install directories as plain strings
#   3. the Windows uninstall registry has Blizzard's proper display names
# Product codes are internal ("prometheus" is Overwatch), so we map the common ones.
BNET_PRODUCTS = {
    "pro": "Overwatch 2", "prometheus": "Overwatch 2", "wlby": "Crash Bandicoot 4",
    "d3": "Diablo III", "osi": "Diablo II: Resurrected", "fen": "Diablo IV", "fenris": "Diablo IV",
    "anbs": "Diablo Immortal", "s1": "StarCraft Remastered", "s2": "StarCraft II",
    "wow": "World of Warcraft", "wow_classic": "World of Warcraft Classic",
    "hero": "Heroes of the Storm", "heroes": "Heroes of the Storm",
    "hs_beta": "Hearthstone", "hsb": "Hearthstone", "w3": "Warcraft III: Reforged",
    "odin": "Call of Duty: Modern Warfare", "lazr": "Call of Duty: Modern Warfare II",
    "zeus": "Call of Duty: Black Ops Cold War", "viper": "Call of Duty: Black Ops 4",
    "auks": "Call of Duty: Vanguard", "spot": "Call of Duty: Modern Warfare III",
    "rtro": "Blizzard Arcade Collection", "gryphon": "Warcraft Rumble",
}


def _bnet_installed_codes() -> set[str]:
    path = os.path.join(os.environ.get("APPDATA", ""), "Battle.net", "Battle.net.config")
    try:
        cfg = json.load(open(path, encoding="utf-8", errors="ignore"))
    except (OSError, ValueError):
        return set()
    games = (cfg.get("Games") or {})
    # entries with a recorded install or last-played build are actually installed
    return {code for code, data in games.items() if isinstance(data, dict) and code != "battle_net"}


def scan_battlenet() -> list[Found]:
    if not IS_WIN:
        return []
    out: dict[str, Found] = {}

    def add(title: str | None, path: str | None = None):
        if title and title.lower() not in out:
            out[title.lower()] = Found(title, "battlenet", None, path)

    # 1. product codes from the launcher's config
    for code in _bnet_installed_codes():
        name = BNET_PRODUCTS.get(code) or BNET_PRODUCTS.get(code.split("_")[0])
        if name:
            add(name)

    # 2. install directories from product.db
    db = os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"), "Battle.net", "Agent", "product.db")
    if os.path.exists(db):
        blob = open(db, "rb").read()
        for m in re.finditer(rb"[A-Za-z]:\\[^\x00-\x1f]{3,120}", blob):
            path = m.group().decode("utf-8", "ignore").rstrip("\\")
            base = os.path.basename(path)
            if os.path.isdir(path) and base and base.lower() not in ("battle.net", "agent", "program files", "program files (x86)"):
                add(base, path)

    # 3. Blizzard's own uninstall entries carry the real display names
    for title, path, publisher in _uninstall_entries():
        if "blizzard" in publisher.lower():
            add(title, path)

    return list(out.values())


# ------------------------------------------------- Windows uninstall registry
# A catch-all for launcher games that register an uninstaller: Blizzard, Riot,
# Rockstar and others. Filtered by publisher so we don't list every application
# on the machine.
PUBLISHER_PLATFORM = {
    "blizzard": "battlenet",
    "riot games": "other",
    "rockstar games": "other",
    "gog.com": "gog",
    "ubisoft": "ubisoft",
    "electronic arts": "ea",
    "epic games": "epic",
}
# The uninstall registry lists a publisher's own tooling alongside their games,
# so this filter has to be strict: anything that smells like a launcher, runtime,
# SDK or service is not a game. Better to miss an odd title (the launcher-specific
# scanners above usually catch it) than to fill someone's library with plumbing.
SKIP_PATTERNS = re.compile(
    r"\b(launcher|client|app|service|services|sdk|runtime|redistributable|redist|"
    r"directx|visual c\+\+|\.net|framework|driver|drivers|tool|tools|toolkit|editor|"
    r"anti-?cheat|vanguard|easyanticheat|battleye|overlay|companion|installer|updater|"
    r"setup|uninstall|support|helper|agent|bootstrapper|prerequisites|vc_redist|"
    r"crash handler|dev kit|devkit|engine|studio|creator|workshop|beta test)\b",
    re.I,
)
# exact names that don't trip the patterns above
SKIP_EXACT = {
    "battle.net", "epic games", "rockstar games", "ea", "ubisoft connect", "ubisoft game launcher",
    "gog galaxy", "steam", "riot games", "blizzard entertainment", "xbox", "nvidia geforce experience",
}


def _uninstall_entries() -> list[tuple[str, str, str]]:
    """(display name, install location, publisher) for every uninstall entry."""
    if not IS_WIN:
        return []
    import winreg
    rows: list[tuple[str, str, str]] = []
    for hive, base in (
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ):
        for key in _reg_subkeys(hive, base):
            full = f"{base}\\{key}"
            name = _reg_value(hive, full, "DisplayName")
            if not name:
                continue
            rows.append((str(name), str(_reg_value(hive, full, "InstallLocation") or ""), str(_reg_value(hive, full, "Publisher") or "")))
    return rows


def scan_uninstall_registry() -> list[Found]:
    """Games from publishers we recognise, for launchers with no usable manifest."""
    out: dict[str, Found] = {}
    for title, path, publisher in _uninstall_entries():
        pub = publisher.lower()
        platform = next((v for k, v in PUBLISHER_PLATFORM.items() if k in pub), None)
        if platform is None:
            continue
        low = title.lower().strip()
        if low in out or low in SKIP_EXACT or SKIP_PATTERNS.search(low):
            continue
        # a game folder normally sits under a games directory or has a sizeable
        # install path; publisher tooling usually lives in Program Files directly
        out[low] = Found(title, platform, None, path or None)
    return list(out.values())


# ------------------------------------------------------------ Xbox / Game Pass
def scan_xbox() -> list[Found]:
    if not IS_WIN:
        return []
    # Ask PowerShell for installed Appx packages; a game is any package whose
    # folder has a MicrosoftGame.config (that's the GDK marker Xbox app uses)
    cmd = ["powershell", "-NoProfile", "-Command",
           "Get-AppxPackage | Where-Object { $_.InstallLocation -and (Test-Path (Join-Path $_.InstallLocation 'MicrosoftGame.config')) } "
           "| Select-Object Name, InstallLocation | ConvertTo-Json -Compress"]
    try:
        raw = subprocess.run(cmd, capture_output=True, text=True, timeout=60).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return []
    if not raw:
        return []
    pkgs = json.loads(raw)
    pkgs = pkgs if isinstance(pkgs, list) else [pkgs]
    out = []
    for p in pkgs:
        title = _xbox_display_name(p["InstallLocation"]) or re.sub(r"^[^.]+\.", "", p["Name"])
        if title.endswith(" Launcher"):  # the Minecraft Launcher package sits beside the actual game
            continue
        cover, mime = _xbox_logo(p["InstallLocation"])
        out.append(Found(title, "xbox", None, p["InstallLocation"], cover, mime, _xbox_store_id(p["InstallLocation"])))
    return out


def _xbox_store_id(folder: str) -> str | None:
    """The 12-character Store product id (e.g. 9NBLGGH4R315) lives in MicrosoftGame.config."""
    try:
        text = open(os.path.join(folder, "MicrosoftGame.config"), encoding="utf-8", errors="ignore").read()
    except OSError:
        return None
    m = re.search(r"<StoreId>\s*([0-9A-Z]{12})\s*</StoreId>", text, re.I)
    return m.group(1).upper() if m else None


MAX_COVER_BYTES = 400_000


def _xbox_logo(folder: str) -> tuple[str | None, str | None]:
    """
    Last-resort artwork from inside the package: the square tile logos only.
    (Splash screens and wide logos are backdrops, not covers.) The real poster
    comes from the Store catalogue via store_id; this is for games the Store
    no longer lists. Files often carry a `.scale-200` suffix, so glob for them.
    """
    candidates: list[str] = []
    for fname, patterns in (
        ("MicrosoftGame.config", [r"Square480x480Logo=\"([^\"]+)\"", r"Square150x150Logo=\"([^\"]+)\""]),
        ("AppxManifest.xml", [r"Square310x310Logo=\"([^\"]+)\"", r"Square150x150Logo=\"([^\"]+)\""]),
    ):
        try:
            text = open(os.path.join(folder, fname), encoding="utf-8", errors="ignore").read()
        except OSError:
            continue
        for pat in patterns:
            candidates += re.findall(pat, text)

    for rel in candidates:
        base = os.path.join(folder, rel.replace("\\", os.sep).replace("/", os.sep))
        stem, ext = os.path.splitext(base)
        # exact name, then scale variants, biggest first
        paths = [base] + sorted(glob.glob(f"{stem}.scale-*{ext}"), key=lambda p: -os.path.getsize(p))
        for path in paths:
            if os.path.isfile(path) and os.path.getsize(path) <= MAX_COVER_BYTES:
                mime = "image/png" if ext.lower() == ".png" else "image/jpeg"
                return base64.b64encode(open(path, "rb").read()).decode("ascii"), mime
    return None, None


def _xbox_display_name(folder: str) -> str | None:
    """MicrosoftGame.config carries the real title; fall back to the package name."""
    try:
        text = open(os.path.join(folder, "MicrosoftGame.config"), encoding="utf-8", errors="ignore").read()
    except OSError:
        return None
    m = re.search(r"<ShellVisuals[^>]*DefaultDisplayName=\"([^\"]+)\"", text)
    return m.group(1) if m and not m.group(1).startswith("ms-resource") else None


# ---------------------------------------------------------------------- main
SCANNERS = [scan_steam, scan_epic, scan_gog, scan_ubisoft, scan_ea, scan_battlenet, scan_xbox, scan_uninstall_registry]


def scan_all() -> list[Found]:
    """Every scanner, deduped by (normalised title) so two sources don't both report a game."""
    found: list[Found] = []
    seen: set[str] = set()
    for fn in SCANNERS:
        try:
            items = fn()
        except Exception as e:  # one broken launcher shouldn't kill the whole scan
            print(f"  ! {fn.__name__} failed: {e}", file=sys.stderr)
            continue
        for item in items:
            key = re.sub(r"[^a-z0-9]", "", item.title.lower())
            if key and key not in seen:
                seen.add(key)
                found.append(item)
    return found


def push(found: list[Found], base_url: str) -> None:
    email = input("PlayNext email: ")
    password = getpass.getpass("Password: ")
    body = urllib.parse.urlencode({"username": email, "password": password}).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(f"{base_url}/auth/login", data=body)) as r:
            token = json.load(r)["access_token"]
    except urllib.error.HTTPError as e:
        sys.exit(f"Login failed: {e.read().decode()}")

    payload = json.dumps({"games": [asdict(f) for f in found]}).encode()
    req = urllib.request.Request(f"{base_url}/library/import", data=payload,
                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req) as r:
        result = json.load(r)
    print(f"\nDone. {result['imported']} added, {result['updated']} already there, {result['skipped']} skipped.")


def main() -> None:
    ap = argparse.ArgumentParser(description="Detect installed games and send them to PlayNext")
    ap.add_argument("--json", action="store_true", help="print JSON instead of a table")
    ap.add_argument("--push", action="store_true", help="upload to your PlayNext account without asking")
    ap.add_argument("--url", default=os.environ.get("PLAYNEXT_URL", "http://localhost:8000"), help="PlayNext API base URL")
    args = ap.parse_args()

    # no flags at all almost certainly means someone double-clicked the file,
    # so behave like an app: show results, offer to send, wait before closing
    interactive = len(sys.argv) == 1

    print("Scanning launchers…", file=sys.stderr)
    games = scan_all()

    if args.json:
        print(json.dumps([{k: v for k, v in asdict(g).items() if k != "cover_data"} | {"has_cover": bool(g.cover_data)} for g in games], indent=2))
    else:
        by: dict[str, list[str]] = {}
        for g in games:
            by.setdefault(g.platform, []).append(g.title)
        for plat, titles in sorted(by.items()):
            print(f"\n{plat} ({len(titles)})")
            for t in sorted(titles):
                print(f"  {t}")
        with_art = sum(1 for g in games if g.cover_data)
        if with_art:
            print(f"\n(found local artwork for {with_art} of them)")
        print(f"\n{len(games)} games found on this machine.")

    if not games:
        print("\nNo launchers detected. If you have games installed, please report this as a bug with your launcher list.")
    elif args.push or (interactive and input("\nSend these to PlayNext? [Y/n] ").strip().lower() in ("", "y", "yes")):
        try:
            push(games, args.url.rstrip("/"))
        except urllib.error.URLError as e:
            print(f"\nCouldn't reach PlayNext at {args.url} - is the backend running? ({e.reason})")

    if interactive:
        input("\nPress Enter to close.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
