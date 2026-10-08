"""Check actual built bundle locale and nonempty intent metadata; no Siri claim."""
import json
from pathlib import Path
import plistlib

ROOT = Path(__file__).resolve().parents[1]


def inspect(app):
    bundles = [app, app / "PlugIns/BoxShare.appex", app / "PlugIns/BoxWidgets.appex"]
    for bundle in bundles:
        with (bundle / "Info.plist").open("rb") as source:
            if plistlib.load(source).get("CFBundleDevelopmentRegion") != "ja":
                raise ValueError("Built bundle does not declare Japanese development language")
    for bundle in [app, app / "PlugIns/BoxWidgets.appex"]:
        metadata = bundle / "Metadata.appintents"
        if not metadata.is_dir() or not any(path.is_file() and path.stat().st_size > 0 for path in metadata.rglob("*")):
            raise ValueError("Built app or Widget lacks nonempty extracted intent metadata")
    return {"built_bundles_declare_ja": True, "app_and_widget_intent_metadata_nonempty": True,
            "siri_or_shortcuts_ui_verified": False}


if __name__ == "__main__":
    print(json.dumps(inspect(ROOT / "DerivedData/Build/Products/Debug-iphonesimulator/AtodeYaruBox.app")))
