#!/bin/sh
# Build the scratch repo the README clip is recorded in, then capture the real
# output of brief, recall and show into capture/. Run from an empty directory:
#
#   sh docs/demo/setup_demo.sh /path/to/empty/dir
#
# Then:  python make_cast.py capture mneme-demo.cast
#        python render_gif.py mneme-demo.cast mneme-demo.gif   (needs Pillow)
set -e
DIR="${1:?usage: setup_demo.sh <empty dir>}"
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"
git init -q -b main .
mkdir -p src/auth && echo "# session" > src/auth/session.py
git add -A && git -c user.name=demo -c user.email=demo@example.com commit -qm scaffold

mneme init
mneme new learning --title "Browser storage is readable by scripts" \
  --tried "Kept the session token in localStorage" \
  --result "Any script on the page could read it" \
  --takeaway "Anything kept in browser storage can be read by any script on the page" \
  --summary "Anything kept in browser storage can be read by any script on the page" \
  --keywords localStorage,xss --links src/auth/
Q=$(mneme new question --text "Where should session tokens live?" --links src/auth/session.py | awk '{print $2}')
D=$(mneme new decision --title "Session token storage" \
  --context "Browser storage is exposed to script access" \
  --decision "Use secure, HTTP-only cookies" \
  --summary "Session tokens stay out of browser storage" \
  --keywords cookie,token --links src/auth/session.py | awk '{print $2}')
mneme new reminder --action "Rotate the cookie signing key" \
  --trigger "before the first public release" \
  --summary "Rotate the cookie signing key before release"
mneme resolve "$Q" --answer "HTTP-only cookies" --decision "$D"
mneme handover --summary "Moved session tokens to HTTP-only cookies" \
  --done "Cookie-based sessions pass the auth tests" \
  --next "Remove the localStorage fallback in src/auth/session.py"
git add -A && git -c user.name=demo -c user.email=demo@example.com commit -qm memory

mkdir -p "$HERE/capture"
mneme brief > "$HERE/capture/brief.txt"
mneme recall --path src/auth/ > "$HERE/capture/recall.txt"
mneme show "$D" > "$HERE/capture/show.txt"
echo "captured into $HERE/capture (decision id: $D; update STEPS in make_cast.py if it changed)"
