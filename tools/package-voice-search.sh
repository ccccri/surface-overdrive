#!/bin/bash
# The Firefox voice search extension as a package for addons.mozilla.org: the same files the image installs, linted with
# Mozilla's web-ext and zipped into build/voice-search-for-google-<version>.zip.
set -euo pipefail
repo=$(cd "$(dirname "$0")/.." && pwd)
src="$repo/image/rootfs/usr/share/mozilla/extensions/{ec8030f7-c20a-464f-9b0e-13a3a9e97384}/voice-search@surfaceoverdrive.org"
version=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['version'])" "$src/manifest.json")
out="$repo/build/voice-search-for-google-$version.zip"
mkdir -p "$repo/build"
npx --yes web-ext lint --source-dir "$src" --self-hosted=false
rm -f "$out"
(cd "$src" && zip -q -X -r "$out" . -x '.*')
echo "$out"
