#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-}"
if [[ -z "$PYTHON" ]]; then
  if [[ -x .venv/bin/python ]]; then
    PYTHON=".venv/bin/python"
  else
    PYTHON="python3"
  fi
fi

echo "== Release readiness verification =="

"$PYTHON" - <<'PY'
import sys
minimum = (3, 9)
current = sys.version_info[:2]
if current < minimum:
    raise SystemExit(
        f"Python {minimum[0]}.{minimum[1]}+ is required; found "
        f"{current[0]}.{current[1]}"
    )
print(f"Python: {sys.version.split()[0]}")
PY

required_files=(
  README.md
  CHANGELOG.md
  release-manifest.yaml
  docs/INSTALLATION.md
  docs/MEDIA_PREPARATION.md
  docs/DISPLAY_DETECTION.md
  docs/ROADMAP.md
  docs/releases/0.1.0-rc1.md
  main.py
  configure_gtk_app.py
  install.sh
)

for path in "${required_files[@]}"; do
  [[ -f "$path" ]] || {
    echo "Missing required file: $path" >&2
    exit 1
  }
done
echo "Required files: OK"

bash_scripts=(install.sh scripts/verify-release-readiness.sh)
while IFS= read -r -d '' path; do
  bash_scripts+=("$path")
done < <(find scripts -maxdepth 1 -type f -name '*.sh' -print0)

for path in "${bash_scripts[@]}"; do
  bash -n "$path"
done
echo "Bash syntax: OK"

mapfile -t manifest_entrypoints < <(
  "$PYTHON" - <<'PYMANIFEST'
from pathlib import Path

try:
    from ruamel.yaml import YAML
    with Path("release-manifest.yaml").open(encoding="utf-8") as stream:
        data = YAML(typ="safe").load(stream)
except ImportError:
    import yaml
    with Path("release-manifest.yaml").open(encoding="utf-8") as stream:
        data = yaml.safe_load(stream)

for path in data.get("entrypoints", []):
    if str(path).endswith(".py"):
        print(path)
PYMANIFEST
)

"$PYTHON" -m compileall -q \
  "${manifest_entrypoints[@]}" \
  library \
  tests
echo "Python compilation: OK"

"$PYTHON" - <<'PY'
from pathlib import Path

try:
    from ruamel.yaml import YAML
    with Path("release-manifest.yaml").open(encoding="utf-8") as stream:
        data = YAML(typ="safe").load(stream)
except ImportError:
    import yaml
    with Path("release-manifest.yaml").open(encoding="utf-8") as stream:
        data = yaml.safe_load(stream)

required = {
    "schema_version",
    "release",
    "runtime",
    "platforms",
    "external_tools",
    "hardware",
    "protocols",
    "entrypoints",
    "documentation",
    "known_limitations",
}
missing = sorted(required - set(data or {}))
if missing:
    raise SystemExit(f"Manifest missing fields: {', '.join(missing)}")
if data["release"].get("published") is not False:
    raise SystemExit("Release candidate must not be marked published.")
if not data["hardware"].get("native_media_validated"):
    raise SystemExit("Validated hardware profile is missing.")
print("Release manifest: OK")
PY

"$PYTHON" -m unittest discover -v
echo "Unit tests: OK"

git diff --check
echo "Whitespace: OK"

if command -v ffmpeg >/dev/null 2>&1 && command -v ffprobe >/dev/null 2>&1; then
  optional_tests=(
    scripts/test-media-preparation.py
    scripts/test-media-preparation-advanced.py
    scripts/test-media-profiles.py
  )
  for path in "${optional_tests[@]}"; do
    if [[ -f "$path" ]]; then
      echo "Running optional FFmpeg integration: $path"
      "$PYTHON" "$path"
    fi
  done
  echo "FFmpeg integrations: OK"
else
  echo "FFmpeg integrations: SKIPPED (ffmpeg/ffprobe not both available)"
fi

echo "Release readiness verification passed."
