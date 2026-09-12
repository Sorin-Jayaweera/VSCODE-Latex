#!/usr/bin/env python3
"""
pack_vsix.py -- Package this folder as a .vsix without needing npm or vsce.

A .vsix is a zip with a content-types file, a manifest, and the extension
under extension/. Then:

    python tools/obsidian-preview/pack_vsix.py
    code --install-extension tools/obsidian-preview/obsidian-embeds-preview-0.1.0.vsix
"""

import json
import sys
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent

CONTENT_TYPES = (
    '<?xml version="1.0" encoding="utf-8"?>\n'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension=".json" ContentType="application/json"/>'
    '<Default Extension=".js" ContentType="application/javascript"/>'
    '<Default Extension=".vsixmanifest" ContentType="text/xml"/>'
    '<Default Extension=".md" ContentType="text/markdown"/>'
    '</Types>'
)

MANIFEST = """<?xml version="1.0" encoding="utf-8"?>
<PackageManifest Version="2.0.0" xmlns="http://schemas.microsoft.com/developer/vsx-schema/2011" xmlns:d="http://schemas.microsoft.com/developer/vsx-schema-design/2011">
  <Metadata>
    <Identity Language="en-US" Id="{name}" Version="{version}" Publisher="{publisher}" />
    <DisplayName>{display}</DisplayName>
    <Description xml:space="preserve">{description}</Description>
    <Tags></Tags>
    <Categories>Other</Categories>
    <GalleryFlags>Public</GalleryFlags>
    <Properties>
      <Property Id="Microsoft.VisualStudio.Code.Engine" Value="{engine}" />
      <Property Id="Microsoft.VisualStudio.Code.ExtensionDependencies" Value="" />
      <Property Id="Microsoft.VisualStudio.Code.ExtensionPack" Value="" />
      <Property Id="Microsoft.VisualStudio.Code.ExtensionKind" Value="workspace" />
      <Property Id="Microsoft.VisualStudio.Code.LocalizedLanguages" Value="" />
    </Properties>
  </Metadata>
  <Installation>
    <InstallationTarget Id="Microsoft.VisualStudio.Code"/>
  </Installation>
  <Dependencies/>
  <Assets>
    <Asset Type="Microsoft.VisualStudio.Code.Manifest" Path="extension/package.json" Addressable="true" />
  </Assets>
</PackageManifest>
"""


def main():
    pkg = json.loads((HERE / "package.json").read_text(encoding="utf-8"))
    out = HERE / ("%s-%s.vsix" % (pkg["name"], pkg["version"]))

    manifest = MANIFEST.format(
        name=escape(pkg["name"]),
        version=escape(pkg["version"]),
        publisher=escape(pkg["publisher"]),
        display=escape(pkg.get("displayName", pkg["name"])),
        description=escape(pkg.get("description", "")),
        engine=escape(pkg["engines"]["vscode"]),
    )

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES)
        z.writestr("extension.vsixmanifest", manifest)
        z.write(HERE / "package.json", "extension/package.json")
        z.write(HERE / "extension.js", "extension/extension.js")

    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
