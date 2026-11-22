#!/usr/bin/env bash
# builds PRISMO.ipa (unsigned, SideStore signs it with your Apple ID) onto the Desktop
set -euo pipefail
cd "$(dirname "$0")"
export PATH=/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin
export DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer

[ -f PRISMO/Assets.xcassets/AppIcon.appiconset/icon.png ] || swift icon.swift PRISMO/Assets.xcassets/AppIcon.appiconset/icon.png
xcodegen generate -q
rm -rf build
xcodebuild -project PRISMO.xcodeproj -scheme PRISMO -configuration Release -sdk iphoneos \
  -destination 'generic/platform=iOS' -derivedDataPath build \
  CODE_SIGNING_ALLOWED=NO CODE_SIGNING_REQUIRED=NO CODE_SIGN_IDENTITY="" build -quiet
rm -rf Payload && mkdir Payload
cp -R build/Build/Products/Release-iphoneos/PRISMO.app Payload/
rm -f ~/Desktop/PRISMO.ipa
zip -qry ~/Desktop/PRISMO.ipa Payload
rm -rf Payload
echo "PRISMO.ipa is on the Desktop"
