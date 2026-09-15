#!/bin/bash
set -euo pipefail
best_path=""
best_ver=""
for app in /Applications/Xcode*.app; do
    [ -d "$app" ] || continue
    case "$(printf '%s' "$app" | tr '[:upper:]' '[:lower:]')" in
        *beta*|*_rc*) continue ;;
    esac
    ver=$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$app/Contents/Info.plist" 2>/dev/null || true)
    [ -n "$ver" ] || continue
    if [ -z "$best_ver" ] || [ "$(printf '%s\n%s\n' "$best_ver" "$ver" | sort -V | tail -1)" = "$ver" ]; then
        best_ver="$ver"
        best_path="$app"
    fi
done
[ -n "$best_path" ] || { echo '::error::No stable Xcode found'; exit 1; }
sudo xcode-select -s "$best_path"
xcodebuild -version
command -v xcbeautify >/dev/null || brew install xcbeautify
