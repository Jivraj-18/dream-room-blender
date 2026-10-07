#!/usr/bin/env bash
set -euo pipefail
blender_repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ "$(uname -s)" != Linux || "$(uname -m)" != x86_64 ]]; then
  echo 'This installer supports Linux x64. Install Blender for your platform from https://www.blender.org/download/.' >&2
  exit 1
fi
blender_install_dir="$blender_repo_dir/.tools/blender"
blender_archive_name=blender-5.2.2-linux-x64.tar.xz
blender_expected_sha=84098912789dc450e95697c4184fb8a90acbe5111c2ba4aede3fecb57806a168
blender_binary="$blender_install_dir/blender-5.2.2-linux-x64/blender"
mkdir -p "$blender_install_dir/downloads" "$blender_install_dir/cache"
if [[ ! -x "$blender_binary" ]]; then
  curl --fail --location --retry 2 \
    "https://download.blender.org/release/Blender5.2/$blender_archive_name" \
    --output "$blender_install_dir/downloads/$blender_archive_name"
  printf '%s  %s\n' "$blender_expected_sha" "$blender_install_dir/downloads/$blender_archive_name" | sha256sum --check
  tar -xJf "$blender_install_dir/downloads/$blender_archive_name" -C "$blender_install_dir"
fi
"$blender_binary" --version
