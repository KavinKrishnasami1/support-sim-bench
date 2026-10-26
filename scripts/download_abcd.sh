#!/usr/bin/env bash
# Download the pinned ABCD files used to derive the tasks (MIT license) into data/raw/abcd/.
# Only needed to read the source conversations; running the benchmark does not need them.
set -euo pipefail
COMMIT=6b8700ce67c6b37b062dd7a60abc76d7ef832a97
DIR="$(cd "$(dirname "$0")/.." && pwd)/data/raw/abcd"
mkdir -p "$DIR"
for f in data/abcd_v1.1.json.gz data/guidelines.json LICENSE; do
  curl -sSL -o "$DIR/$(basename "$f")" "https://raw.githubusercontent.com/asappresearch/abcd/$COMMIT/$f"
done
cd "$DIR"
echo "2bdf53ac359543dcdc38d55bc6513e78df120363f8f44870716e909f4606de15  abcd_v1.1.json.gz" | shasum -a 256 -c -
echo "3ab7e179a7f13027b7bc64293541f0e9beacca3701cade67fb8fce78c2d9317b  LICENSE" | shasum -a 256 -c -
