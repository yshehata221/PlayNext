# PlayNext scanner

Detects every game installed on this PC across Steam, Epic, GOG, Ubisoft Connect, EA app, Battle.net, Xbox / Game Pass, and anything else registered by a publisher we recognise (Blizzard, Riot, Rockstar), then adds them to your PlayNext library. Nothing leaves your machine except game titles, the launcher they came from, and (for Game Pass titles) the store ID so the proper poster can be fetched.

Battle.net games are found three ways, since the launcher keeps its records in a binary blob: the product codes in `Battle.net.config`, the install paths inside `product.db`, and Blizzard's own entries in the Windows uninstall registry.

```
python playnext_scan.py          # just look
python playnext_scan.py --push   # send to your account (asks for your login)
```

Set `PLAYNEXT_URL` (or pass `--url`) to point at a deployed instance.

## Build a one-file .exe

```
pip install pyinstaller
pyinstaller --onefile --name playnext-scan playnext_scan.py
```

`dist/playnext-scan.exe` runs with no Python install. Double-clicking it opens a console, scans, and prompts for your login.

## What it can and can't see

- Installed games only. Owned-but-not-installed comes from the launcher's own API, which for most of these launchers is private. Steam is the exception, and PlayNext handles that with "Sign in with Steam".
- Ubisoft and Battle.net don't store display names locally, so those come through as folder names ("AssassinsCreedValhalla"). PlayNext's title matching cleans up the common ones; you can rename the rest.
