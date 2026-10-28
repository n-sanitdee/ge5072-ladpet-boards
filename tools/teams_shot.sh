#!/bin/sh
# Screenshot a section's live board for the Teams post (800×462, like CA48/EC30/TS66) and publish it.
#   sh tools/teams_shot.sh wk12 ca50
# Writes <week>/shots/<code>.png (served at https://n-sanitdee.github.io/ge5072-ladpet-boards/<week>/shots/<code>.png,
# which the Teams page can fetch) and a copy in OneDrive Teaching/Teams_Post_Images/.
set -e
week=$1; code=$2
cd "$(dirname "$0")/.."
tmp=$(mktemp -d)
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --disable-gpu --hide-scrollbars \
  --window-size=1386,800 --virtual-time-budget=8000 --screenshot="$tmp/raw.png" \
  "https://n-sanitdee.github.io/ge5072-ladpet-boards/$week/$code.html?t=$(date +%s)" 2>/dev/null
mkdir -p "$week/shots"
python3 -c "
from PIL import Image
Image.open('$tmp/raw.png').convert('RGB').resize((800, 462), Image.LANCZOS).save('$week/shots/$code.png')"
UP=$(echo "$code" | tr a-z A-Z)
cp "$week/shots/$code.png" "$HOME/Library/CloudStorage/OneDrive-UniversityoftheThaiChamberofCommerce/Teaching/Teams_Post_Images/$(echo $week | sed 's/wk/Wk/')_Ladpet_Board_$UP.png"
git add "$week/shots/$code.png"
git commit -qm "$week: $UP board screenshot for the Teams post" || true
git pull -q --rebase && git push -q
want=$(wc -c < "$week/shots/$code.png" | tr -d ' ')
for i in $(seq 1 90); do  # wait for THIS file (Pages caches the old one for up to ~10 min)
  [ "$(curl -s "https://n-sanitdee.github.io/ge5072-ladpet-boards/$week/shots/$code.png?t=$i$(date +%s)" | wc -c | tr -d ' ')" = "$want" ] && echo "published: $week/shots/$code.png" && exit 0
  sleep 10
done
echo "pushed, but not served yet"
