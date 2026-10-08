"""Deterministic, dependency-free Xcode project generation. Run by the agent/CI."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "AtodeYaruBox.xcodeproj"
OBJECTS: dict[str, dict] = {}


def uid(key: str) -> str:
    return hashlib.sha1(key.encode()).hexdigest()[:24].upper()


def add(key: str, isa: str, **fields) -> str:
    identifier = uid(key)
    OBJECTS[identifier] = {"isa": isa, **fields}
    return identifier


def encode(value, depth=0):
    indent = "\t" * depth
    if isinstance(value, dict):
        rows = ["{"]
        for key, item in value.items():
            rows.append("\t" * (depth + 1) + json.dumps(str(key)) + " = " + encode(item, depth + 1) + ";")
        return "\n".join(rows) + "\n" + indent + "}"
    if isinstance(value, list):
        return "(\n" + "\n".join("\t" * (depth + 1) + encode(item, depth + 1) + "," for item in value) + "\n" + indent + ")"
    if isinstance(value, int):
        return str(value)
    return json.dumps(str(value), ensure_ascii=False)


def files(folder: str):
    return sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / folder).rglob("*.swift"))


def main():
    OBJECTS.clear()
    configs = sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / "Config").glob("*"))
    asset_dir = "AtodeYaruBox/Resources/Assets.xcassets"
    shortcut_catalog = "AtodeYaruBox/Resources/AppShortcuts.xcstrings"
    color_dir = "Shared/Resources/Colors.xcassets"
    groups = {
        "App": files("AtodeYaruBox"), "Shared": files("Shared"), "ShareExtension": files("ShareExtension"),
        "Widgets": files("Widgets"), "Tests": files("Tests"), "UITests": files("UITests"), "Config": configs + [color_dir],
    }
    all_files = sorted({p for values in groups.values() for p in values} | {asset_dir, shortcut_catalog})
    for path in all_files:
        kind = "sourcecode.swift" if path.endswith(".swift") else "text"
        if path.endswith(".plist") or path.endswith(".entitlements") or path.endswith(".xcprivacy"): kind = "text.plist.xml"
        if path.endswith(".xcconfig"): kind = "text.xcconfig"
        if path.endswith(".xcassets"): kind = "folder.assetcatalog"
        if path.endswith(".xcstrings"): kind = "text.json.xcstrings"
        add("file:" + path, "PBXFileReference", lastKnownFileType=kind, path=path, sourceTree="<group>")
    groups["App"].append(asset_dir)
    groups["Config"].append(shortcut_catalog)
    children = []
    for name, paths in groups.items():
        children.append(add("group:" + name, "PBXGroup", name=name, children=[uid("file:" + p) for p in paths], sourceTree="<group>"))

    target_specs = [
        ("AtodeYaruBox", "com.apple.product-type.application", ".app", groups["App"][:-1] + groups["Shared"] + ["ShareExtension/ShareImportService.swift"], "App", "$(APP_BUNDLE_ID)"),
        ("BoxShare", "com.apple.product-type.app-extension", ".appex", groups["ShareExtension"] + [p for p in groups["Shared"] if not p.endswith("AppIntents.swift")] + ["AtodeYaruBox/Services/OCRService.swift"], "Share", "$(APP_BUNDLE_ID).share"),
        ("BoxWidgets", "com.apple.product-type.app-extension", ".appex", groups["Widgets"] + groups["Shared"], "Widgets", "$(APP_BUNDLE_ID).widgets"),
        ("AtodeYaruBoxTests", "com.apple.product-type.bundle.unit-test", ".xctest", groups["Tests"], None, "$(APP_BUNDLE_ID).tests"),
        ("AtodeYaruBoxUITests", "com.apple.product-type.bundle.ui-testing", ".xctest", groups["UITests"], None, "$(APP_BUNDLE_ID).uitests"),
    ]
    product_refs = []
    targets = []
    for name, product_type, suffix, sources, info_name, bundle in target_specs:
        product_refs.append(add("product:" + name, "PBXFileReference", explicitFileType="wrapper.application" if suffix == ".app" else ("wrapper.app-extension" if suffix == ".appex" else "wrapper.cfbundle"), includeInIndex=0, path=name + suffix, sourceTree="BUILT_PRODUCTS_DIR"))
        build_files = [add("build:" + name + ":" + p, "PBXBuildFile", fileRef=uid("file:" + p)) for p in sources]
        phases = [add("sources:" + name, "PBXSourcesBuildPhase", buildActionMask=2147483647, files=build_files, runOnlyForDeploymentPostprocessing=0)]
        phases.append(add("frameworks:" + name, "PBXFrameworksBuildPhase", buildActionMask=2147483647, files=[], runOnlyForDeploymentPostprocessing=0))
        resources = []
        if info_name:
            resources.append(add("resource:" + name + ":privacy", "PBXBuildFile", fileRef=uid("file:Config/PrivacyInfo.xcprivacy")))
            resources.append(add("resource:" + name + ":colors", "PBXBuildFile", fileRef=uid("file:" + color_dir)))
        if name == "AtodeYaruBox":
            resources.append(add("resource:" + name + ":assets", "PBXBuildFile", fileRef=uid("file:" + asset_dir)))
            resources.append(add("resource:" + name + ":shortcuts", "PBXBuildFile", fileRef=uid("file:" + shortcut_catalog)))
        phases.append(add("resources:" + name, "PBXResourcesBuildPhase", buildActionMask=2147483647, files=resources, runOnlyForDeploymentPostprocessing=0))
        dependencies = []
        needed = ["BoxShare", "BoxWidgets"] if name == "AtodeYaruBox" else (["AtodeYaruBox"] if info_name is None else [])
        for dependency in needed:
            proxy = add("proxy:" + name + ":" + dependency, "PBXContainerItemProxy", containerPortal=uid("project"), proxyType=1, remoteGlobalIDString=uid("target:" + dependency), remoteInfo=dependency)
            dependencies.append(add("dependency:" + name + ":" + dependency, "PBXTargetDependency", target=uid("target:" + dependency), targetProxy=proxy))
        if name == "AtodeYaruBox":
            embed = [add("embed:" + extension, "PBXBuildFile", fileRef=uid("product:" + extension), settings={"ATTRIBUTES": ["CodeSignOnCopy", "RemoveHeadersOnCopy"]}) for extension in ["BoxShare", "BoxWidgets"]]
            phases.append(add("embed-phase", "PBXCopyFilesBuildPhase", buildActionMask=2147483647, dstPath="", dstSubfolderSpec=13, files=embed, name="Embed App Extensions", runOnlyForDeploymentPostprocessing=0))
        target_configs = []
        for configuration in ["Debug", "Release"]:
            settings = {
                "PRODUCT_NAME": "$(TARGET_NAME)", "PRODUCT_BUNDLE_IDENTIFIER": bundle, "SDKROOT": "iphoneos",
                "SUPPORTED_PLATFORMS": "iphoneos iphonesimulator", "SWIFT_VERSION": "5.0",
                "TARGETED_DEVICE_FAMILY": "1", "IPHONEOS_DEPLOYMENT_TARGET": "17.0",
                "LD_RUNPATH_SEARCH_PATHS": ["$(inherited)", "@executable_path/Frameworks", "@executable_path/../../Frameworks"],
                "SWIFT_OPTIMIZATION_LEVEL": "-Onone" if configuration == "Debug" else "-O",
                "SWIFT_ACTIVE_COMPILATION_CONDITIONS": "DEBUG" if configuration == "Debug" else "",
                "ENABLE_TESTABILITY": "YES" if configuration == "Debug" else "NO",
                "DEBUG_INFORMATION_FORMAT": "dwarf" if configuration == "Debug" else "dwarf-with-dsym",
                "SWIFT_STRICT_CONCURRENCY": "targeted",
            }
            if info_name:
                settings.update({"INFOPLIST_FILE": "Config/" + info_name + "-Info.plist", "CODE_SIGN_ENTITLEMENTS": "Config/Shared.entitlements"})
                if name != "AtodeYaruBox": settings.update({"APPLICATION_EXTENSION_API_ONLY": "YES", "SKIP_INSTALL": "YES"})
                else: settings.update({"ASSETCATALOG_COMPILER_APPICON_NAME": "AppIcon", "ENABLE_PREVIEWS": "YES"})
            else:
                settings["GENERATE_INFOPLIST_FILE"] = "YES"
                if suffix == ".xctest" and "UITests" not in name:
                    settings.update({"TEST_HOST": "$(BUILT_PRODUCTS_DIR)/AtodeYaruBox.app/AtodeYaruBox", "BUNDLE_LOADER": "$(TEST_HOST)"})
                else: settings["TEST_TARGET_NAME"] = "AtodeYaruBox"
            target_configs.append(add("config:" + name + ":" + configuration, "XCBuildConfiguration", baseConfigurationReference=uid("file:Config/App.xcconfig"), buildSettings=settings, name=configuration))
        config_list = add("configs:" + name, "XCConfigurationList", buildConfigurations=target_configs, defaultConfigurationIsVisible=0, defaultConfigurationName="Release")
        targets.append(add("target:" + name, "PBXNativeTarget", buildConfigurationList=config_list, buildPhases=phases, buildRules=[], dependencies=dependencies, name=name, productName=name, productReference=uid("product:" + name), productType=product_type))

    products = add("group:Products", "PBXGroup", children=product_refs, name="Products", sourceTree="<group>")
    main_group = add("group:root", "PBXGroup", children=children + [products], sourceTree="<group>")
    project_configs = []
    for configuration in ["Debug", "Release"]:
        project_configs.append(add("project-config:" + configuration, "XCBuildConfiguration", buildSettings={
            "CLANG_ENABLE_MODULES": "YES", "CLANG_ENABLE_OBJC_ARC": "YES", "CLANG_WARN_DOCUMENTATION_COMMENTS": "YES",
            "CLANG_WARN_QUOTED_INCLUDE_IN_FRAMEWORK_HEADER": "YES", "GCC_WARN_UNUSED_VARIABLE": "YES",
            "SWIFT_VERSION": "5.0", "IPHONEOS_DEPLOYMENT_TARGET": "17.0", "CODE_SIGN_STYLE": "Automatic",
            "ONLY_ACTIVE_ARCH": "YES" if configuration == "Debug" else "NO",
            "COPY_PHASE_STRIP": "NO" if configuration == "Debug" else "YES",
        }, name=configuration))
    project_config_list = add("project-configs", "XCConfigurationList", buildConfigurations=project_configs, defaultConfigurationIsVisible=0, defaultConfigurationName="Release")
    add("project", "PBXProject", attributes={"BuildIndependentTargetsInParallel": "YES", "LastUpgradeCheck": "1600"},
        buildConfigurationList=project_config_list, compatibilityVersion="Xcode 14.0", developmentRegion="ja",
        hasScannedForEncodings=0, knownRegions=["ja", "en", "Base"], mainGroup=main_group, productRefGroup=products,
        projectDirPath="", projectRoot="", targets=targets)
    PROJECT.mkdir(exist_ok=True)
    content = {"archiveVersion": 1, "classes": {}, "objectVersion": 56, "objects": dict(sorted(OBJECTS.items())), "rootObject": uid("project")}
    (PROJECT / "project.pbxproj").write_text("// !$*UTF8*$!\n" + encode(content) + "\n", encoding="utf-8", newline="\n")
    make_scheme()
    print(f"Generated {len(targets)} targets, {len(all_files)} file references, {len(OBJECTS)} objects")


def make_scheme():
    scheme = ET.Element("Scheme", LastUpgradeVersion="1600", version="1.3")
    def ref(parent, name, suffix):
        return ET.SubElement(parent, "BuildableReference", BuildableIdentifier="primary", BlueprintIdentifier=uid("target:" + name), BuildableName=name + suffix, BlueprintName=name, ReferencedContainer="container:AtodeYaruBox.xcodeproj")
    build = ET.SubElement(scheme, "BuildAction", parallelizeBuildables="YES", buildImplicitDependencies="YES")
    entries = ET.SubElement(build, "BuildActionEntries")
    for name, suffix in [("AtodeYaruBox", ".app"), ("AtodeYaruBoxTests", ".xctest"), ("AtodeYaruBoxUITests", ".xctest")]:
        entry = ET.SubElement(entries, "BuildActionEntry", buildForTesting="YES", buildForRunning="YES" if suffix == ".app" else "NO", buildForProfiling="YES" if suffix == ".app" else "NO", buildForArchiving="YES" if suffix == ".app" else "NO", buildForAnalyzing="YES")
        ref(entry, name, suffix)
    test = ET.SubElement(scheme, "TestAction", buildConfiguration="Debug", selectedDebuggerIdentifier="Xcode.DebuggerFoundation.Debugger.LLDB", selectedLauncherIdentifier="Xcode.IDEFoundation.Launcher.LLDB", shouldUseLaunchSchemeArgsEnv="YES")
    testables = ET.SubElement(test, "Testables")
    for name in ["AtodeYaruBoxTests", "AtodeYaruBoxUITests"]:
        ref(ET.SubElement(testables, "TestableReference", skipped="NO"), name, ".xctest")
    launch = ET.SubElement(scheme, "LaunchAction", buildConfiguration="Debug", selectedDebuggerIdentifier="Xcode.DebuggerFoundation.Debugger.LLDB", selectedLauncherIdentifier="Xcode.IDEFoundation.Launcher.LLDB", launchStyle="0", useCustomWorkingDirectory="NO", ignoresPersistentStateOnLaunch="NO", debugDocumentVersioning="YES", allowLocationSimulation="YES")
    ref(ET.SubElement(launch, "BuildableProductRunnable", runnableDebuggingMode="0"), "AtodeYaruBox", ".app")
    profile = ET.SubElement(scheme, "ProfileAction", buildConfiguration="Release", shouldUseLaunchSchemeArgsEnv="YES", savedToolIdentifier="", useCustomWorkingDirectory="NO", debugDocumentVersioning="YES")
    ref(ET.SubElement(profile, "BuildableProductRunnable", runnableDebuggingMode="0"), "AtodeYaruBox", ".app")
    ET.SubElement(scheme, "AnalyzeAction", buildConfiguration="Debug")
    ET.SubElement(scheme, "ArchiveAction", buildConfiguration="Release", revealArchiveInOrganizer="YES")
    ET.indent(scheme)
    folder = PROJECT / "xcshareddata" / "xcschemes"; folder.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(scheme).write(folder / "AtodeYaruBox.xcscheme", encoding="utf-8", xml_declaration=True)


if __name__ == "__main__": main()
