#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo 'Installing Qt 6 development dependencies (Ubuntu/Debian)...'
sudo apt-get update
sudo apt-get install -y --no-install-recommends build-essential cmake qt6-base-dev \
  python3 python3-numpy python3-scipy desktop-file-utils

echo 'Compiling Pytro-NOVA native Qt interface...'
cmake -S . -B build/linux -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr/local
cmake --build build/linux --parallel 2

echo 'Installing Pytro-NOVA and text converter...'
sudo cmake --install build/linux
if command -v update-desktop-database >/dev/null 2>&1; then
  sudo update-desktop-database /usr/local/share/applications || true
fi
printf '\nInstalled. Launch via your app menu (Pytro-NOVA), or run: PytroNOVA\n'
printf 'Convert data: pytro-nova-to-txt file.nox --output ~/Documents\n'
