#!/usr/bin/env bash
# Download the pinned public sources the v4real policy wiki was adapted from (SOURCES.md) and check their SHA-256.
# Files go to data/raw/v4sources/ (gitignored). Nothing here is needed to run the benchmark.
set -euo pipefail
DIR="$(cd "$(dirname "$0")/.." && pwd)/data/raw/v4sources"
mkdir -p "$DIR"
cd "$DIR"
fetch() {  # url file sha256
  curl -sSL -A "Mozilla/5.0" -o "$2" "$1"
  echo "$3  $2" | shasum -a 256 -c -
}
fetch "https://origin-www.gsa.gov/system/files/Access-Control-%28AC%29-%5BCIO-IT-Security-01-07-Rev-8%5D.pdf" \
  gsa_ac_rev8.pdf e41234d552fb48a50ceaafc810e7624f420f50079e3cc3f884ddf9abea631b26
fetch "https://www.gsa.gov/system/files/Identification-and-Authentication-%28IA%29-%5BCIO-IT-Security-01-01-Rev-8%5D.pdf" \
  gsa_ia_rev8.pdf e1c717090459ad111fa37c271ed36b19928259eccf962c58b57d27ce51d7e6c3
fetch "https://www.gsa.gov/system/files/Termination-and-Transfer-%5BCIO-IT-Security-03-23-Rev-6%5D-04-19-2022docx.pdf" \
  gsa_tt_rev6.pdf 0254469ab08df160540b84f7a6c65230818fd7d002d4a81841fbfb14931b9916
MOJ=15c1c838835ee52185fe22134889780b3d7d241a
for f in access-control-policy:e86e40fa00057870591b6083209b4d5974a4f39834e8c376e9eff4eb262b42f6 \
         long-term-leave:7fb6a21d5e73fc3fd423921f63c0fda31030a0915eebe1c8aed75b4cfc701431 \
         accessing-moj-it-systems-from-overseas:c993939f8693494f12096a4122ad3215fed70ff5ed8f47be8efd3ac3e3baa4af \
         acceptable-use-policy:f0c2a94052f0847396fac34c5aa0da5e5687ad74a58eff69ac4378cb9e35ee17 \
         lost-devices-incidents:1da2ebe3dc11d2a237fcb4f6186422d062819919fdb5fb442ad4690b1db7400c \
         privileged-account-management-guide:0d816f79b0943b620c247d4ee36ced5d7ac131406401017f7063c854f39bc181; do
  fetch "https://raw.githubusercontent.com/ministryofjustice/security-guidance/$MOJ/dita/${f%%:*}.dita" "moj_${f%%:*}.dita" "${f##*:}"
done
