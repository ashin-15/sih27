#!/usr/bin/env bash
# Rasterise the Lucide line icons used by build.mjs into assets/icons/*.png.
# Requires ImageMagick 7 (`magick`) and the lucide-static dev dependency.
set -euo pipefail
cd "$(dirname "$0")"

src=node_modules/lucide-static/icons
out=assets/icons
mkdir -p "$out"

render() {
  local name=$1 color=$2
  sed -e "s/currentColor/${color}/g" -e 's/stroke-width="2"/stroke-width="1.75"/' \
    "$src/$name.svg" |
    magick -background none -density 1200 svg:- -resize 256x256 "$out/$name.png"
}

for icon in layers wifi-off laptop truck; do render "$icon" "#2F6B52"; done
for icon in git-branch target shield-check; do render "$icon" "#2F5FA8"; done
echo "icons written to $out"
