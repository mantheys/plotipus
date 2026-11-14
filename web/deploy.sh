#!/usr/bin/env bash
# Publish the static page to GitHub Pages (https://mantheys.github.io/plotipus/): builds build/site
# from web/ and docs/ and force-pushes it as the single commit of gh-pages.
#     bash web/deploy.sh
# CI runs it on main after the tests (.github/workflows/ci.yml), with DEPLOY_REMOTE carrying its token.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"
[ -z "$(git status --porcelain)" ] || { echo "commit first: the site records the main commit it was built from" >&2; exit 1; }
python web/build.py --out build/site
touch build/site/.nojekyll
SITE=$(mktemp -d)
cp -r build/site/. "$SITE"
git -C "$SITE" init -q -b gh-pages
git -C "$SITE" add -A
git -C "$SITE" commit -q -m "plotipus static site, built from main@$(git rev-parse --short HEAD)"
git -C "$SITE" push -q -f "${DEPLOY_REMOTE:-$(git remote get-url origin)}" gh-pages
rm -rf "$SITE"
echo "pushed; GitHub Pages rebuilds https://mantheys.github.io/plotipus/ in about a minute"
