"""Build the release zip: the app's files under git, plus VERSION. The release workflow runs it; so can you.

    python tools/package.py 2026.11.26 teams-remix.zip

Tests, tools and the workflow stay out: the people using the app don't need them.
"""
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEFT_OUT = (".github/", "tests/", "tools/")


def files():
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return [f for f in out.splitlines() if f and not f.startswith(LEFT_OUT) and f != ".gitignore"]


def build(version, out):
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files():
            z.write(ROOT / f, f)
        z.writestr("VERSION", version + "\n")
    return out


if __name__ == "__main__":
    print(build(sys.argv[1], sys.argv[2]))
