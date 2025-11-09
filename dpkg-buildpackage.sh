#!/usr/bin/env bash

#wrapper to run dpkg-buildpackage in a safe place

set -euo pipefail

ROOT=$(pwd)
TMPDIR=$(mktemp -d)
PKGDIR="$TMPDIR/btrfs_care"
cleanup() {
    rm -rf "$TMPDIR"
}
trap cleanup EXIT

mkdir -p "$PKGDIR"
git archive HEAD | tar -C "$PKGDIR" -x
cd "$PKGDIR"

if [ -d fakebin ]; then
    chmod -R a+rX fakebin
fi

dpkg-buildpackage "$@"

cd "$TMPDIR"
mkdir -p "$ROOT/build"
shopt -s nullglob
for artifact in btrfs-care_*; do
    cp -v "$artifact" "$ROOT/build/"
done
