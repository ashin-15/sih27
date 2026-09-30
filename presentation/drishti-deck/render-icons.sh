#!/usr/bin/env bash
# Rasterise the Lucide line icons used by build.mjs into assets/icons/*.png.
# Requires ImageMagick 7 (`magick`) and the lucide-static dev dependency.
set -euo pipefail
cd "$(dirname "$0")"

src=node_modules/lucide-static/icons
out=assets/icons
mkdir -p "$out"

render() {
  local name=$1 color=$2 file=$3
  sed -e "s/currentColor/${color}/g" -e 's/stroke-width="2"/stroke-width="1.75"/' \
    "$src/$name.svg" |
    magick -background none -density 1200 svg:- -resize 256x256 "$out/$file.png"
}

# Navy icons, written as <name>.png.
icons=(
  radar mountain tags grid-3x3 boxes monitor cpu wifi-off laptop scaling git-branch
  shield-check route eye users badge-check map layers target gauge
)
for name in "${icons[@]}"; do render "$name" "#243B53" "$name"; done

# Coloured icons for the impact slide, written as <name>-<hex>.png.
coloured=(
  "trending-up:C0392B" "leaf:3F7D5A" "cog:2F5FA8"
  "hard-hat:D0671F" "graduation-cap:6A4FA0" "users:2A8C8C"
)
for pair in "${coloured[@]}"; do
  name=${pair%%:*}
  hex=${pair#*:}
  render "$name" "#$hex" "$name-$hex"
done
echo "$(( ${#icons[@]} + ${#coloured[@]} )) icons written to $out"
