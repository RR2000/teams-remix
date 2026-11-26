"""Updates from GitHub: is there a newer release, and put it in place with one click.

The version is the release date ('2026.11.26', then '2026.11.26.2' for a second one that day), written by the release
workflow into the VERSION file of the release zip. Nobody types a version by hand. A copy made with `git clone` has no
VERSION file: it is updated with `git pull`, so it is never offered the button.

Updating replaces only the app's own files: everything personal lives in APPDATA. The files being replaced are kept
in APPDATA\\teams-remix\\backup\\<old version> first, so a bad update can be undone by copying them back.
"""
import io
import json
import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path

import teams

REPO = "RR2000/teams-remix"
HERE = Path(__file__).resolve().parent
NEEDED = ("teams_theme.pyw", "server.py", "teams.py", "theme.py", "worker.py", "ui/index.html")  # a real release has them
MAX_ZIP = 20 * 1024 * 1024
BACKUP_DIR = teams.CONFIG_DIR / "backup"


def current_version():
    try:
        return (HERE / "VERSION").read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def is_git_copy():
    return (HERE / ".git").exists()


def parse(v):
    """'v2026.11.26.2' -> (2026, 11, 26, 2); anything else -> None."""
    try:
        return tuple(int(x) for x in str(v).lstrip("v").split("."))
    except ValueError:
        return None


def newer(remote, local):
    r, l = parse(remote), parse(local)
    return bool(r and l and r > l)


def _get(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": "teams-remix-updater", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # the system proxy, if any, is used
        return r.read(MAX_ZIP + 1)


def latest():
    """The newest release on GitHub: {'version', 'notes', 'zip', 'page'}, or None (no release, offline...)."""
    try:
        rel = json.loads(_get(f"https://api.github.com/repos/{REPO}/releases/latest"))
    except (OSError, ValueError):
        return None
    zips = [a["browser_download_url"] for a in rel.get("assets") or [] if str(a.get("name", "")).endswith(".zip")]
    version = str(rel.get("tag_name", "")).lstrip("v")
    if not zips or not parse(version):
        return None
    return {"version": version, "notes": str(rel.get("body") or "")[:4000], "zip": zips[0], "page": rel.get("html_url")}


def check():
    """What the app shows: {'version', 'notes', 'page', 'git'} when a newer release exists, else None."""
    if is_git_copy():
        return None  # the developer's copy: `git pull`
    mine = current_version()
    rel = latest()
    if not rel or not mine or not newer(rel["version"], mine):
        return None
    return {"version": rel["version"], "notes": rel["notes"], "page": rel["page"], "zip": rel["zip"]}


def _safe_names(z):
    for n in z.namelist():
        p = Path(n)
        if p.is_absolute() or ".." in p.parts or n.startswith(("/", "\\")):
            raise ValueError(f"unsafe path in the update: {n}")
    return z.namelist()


def install(data, app_dir=None, backup_dir=None):
    """Put the release zip `data` in place of the app's files. Returns the new version."""
    app_dir = Path(app_dir) if app_dir else HERE
    backup_dir = Path(backup_dir) if backup_dir else BACKUP_DIR  # read now: it can be pointed elsewhere (tests)
    z = zipfile.ZipFile(io.BytesIO(data))
    names = _safe_names(z)
    if not all(n in names for n in NEEDED) or "VERSION" not in names:
        raise ValueError("the update does not look like Teams Remix")
    new = z.read("VERSION").decode("utf-8").strip()
    if not parse(new):
        raise ValueError("the update has no valid version")
    try:
        old = (app_dir / "VERSION").read_text(encoding="utf-8").strip() or None
    except OSError:
        old = None
    with tempfile.TemporaryDirectory() as tmp:  # unpack first: nothing changes if the zip is broken
        z.extractall(tmp)
        keep = Path(backup_dir) / (old or "unknown")
        if keep.exists():
            shutil.rmtree(keep, ignore_errors=True)
        replaced, added = [], []
        try:
            for n in names:
                src, dst = Path(tmp) / n, Path(app_dir) / n
                if src.is_dir():
                    continue
                if dst.exists():
                    (keep / n).parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(dst, keep / n)
                    replaced.append(n)
                else:
                    added.append(n)
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
        except OSError:
            # stopped half way (a file in use, a full disk...): everything goes back as it was
            for n in replaced:
                shutil.copy2(keep / n, Path(app_dir) / n)
            for n in added:
                (Path(app_dir) / n).unlink(missing_ok=True)
            raise
    return new


def download_and_install(zip_url):
    if not zip_url.startswith(f"https://github.com/{REPO}/releases/download/"):
        raise ValueError("update from an unexpected place")
    data = _get(zip_url, timeout=60)
    if len(data) > MAX_ZIP:
        raise ValueError("the update is too large")
    return install(data)
