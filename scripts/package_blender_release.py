#!/usr/bin/env python3
"""Build installable ReQRemeshify ZIPs using the upstream QuadWild native binaries.

The fork repository intentionally keeps platform binaries out of source.  At release
 time this script extracts the known-good binaries from QRemeshify 1.1.0 release
assets and combines them with the current fork source.
"""

from __future__ import annotations

import argparse
import ast
import shutil
import sys
import tempfile
import tomllib
import zipfile
from pathlib import Path

EXPECTED_BINARIES: dict[str, tuple[str, str]] = {
    "windows": ("lib_quadwild.dll", "lib_quadpatches.dll"),
    "linux": ("liblib_quadwild.so", "liblib_quadpatches.so"),
    "macos": ("liblib_quadwild.dylib", "liblib_quadpatches.dylib"),
}

UPSTREAM_ASSET_NAMES: dict[str, str] = {
    platform: f"QRemeshify-1.1.0-{platform}.zip" for platform in EXPECTED_BINARIES
}


def fail(message: str) -> "NoReturn":
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)


def normalized_version(value: str) -> str:
    value = value.strip()
    if value.lower().startswith("v"):
        value = value[1:]
    if not value:
        fail("empty release version")
    return value


def read_bl_info_version(init_file: Path) -> str | None:
    tree = ast.parse(init_file.read_text(encoding="utf-8"), filename=str(init_file))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "bl_info":
                    data = ast.literal_eval(node.value)
                    version = data.get("version")
                    if isinstance(version, tuple) and all(isinstance(x, int) for x in version):
                        return ".".join(str(x) for x in version)
    return None


def verify_source_version(source_dir: Path, version: str) -> None:
    manifest = source_dir / "blender_manifest.toml"
    init_file = source_dir / "__init__.py"
    if not manifest.is_file():
        fail(f"missing {manifest}")
    if not init_file.is_file():
        fail(f"missing {init_file}")

    manifest_version = str(tomllib.loads(manifest.read_text(encoding="utf-8")).get("version", ""))
    if manifest_version != version:
        fail(
            f"tag/version is {version}, but blender_manifest.toml says {manifest_version or '<missing>'}"
        )

    bl_info_version = read_bl_info_version(init_file)
    if bl_info_version and bl_info_version != version:
        fail(f"tag/version is {version}, but bl_info version says {bl_info_version}")


def safe_extract(archive: Path, destination: Path) -> None:
    destination = destination.resolve()
    with zipfile.ZipFile(archive) as zf:
        for member in zf.infolist():
            target = (destination / member.filename).resolve()
            try:
                target.relative_to(destination)
            except ValueError:
                fail(f"unsafe path in {archive.name}: {member.filename}")
        zf.extractall(destination)


def find_binary(root: Path, filename: str) -> Path:
    matches = [path for path in root.rglob(filename) if path.is_file()]
    if not matches:
        fail(f"{filename} not found in extracted upstream asset")
    if len(matches) > 1:
        pretty = ", ".join(str(path) for path in matches)
        fail(f"multiple copies of {filename} found: {pretty}")
    if matches[0].stat().st_size < 1024:
        fail(f"{filename} looks invalid ({matches[0].stat().st_size} bytes)")
    return matches[0]


def copy_source_tree(source_dir: Path, destination: Path) -> None:
    def ignore(_directory: str, names: list[str]) -> set[str]:
        ignored = {name for name in names if name == "__pycache__" or name.endswith((".pyc", ".pyo"))}
        return ignored

    shutil.copytree(source_dir, destination, ignore=ignore)


def add_file(zf: zipfile.ZipFile, source: Path, arcname: str) -> None:
    info = zipfile.ZipInfo.from_file(source, arcname=arcname)
    # Explicitly use deflate for source/config files while native libraries can
    # still be compressed by zipfile efficiently enough for release assets.
    with source.open("rb") as handle:
        zf.writestr(info, handle.read(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def write_zip(source_root: Path, output: Path, nested_folder: bool) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w") as zf:
        for path in sorted(source_root.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(source_root).as_posix()
            arcname = f"QRemeshify/{relative}" if nested_folder else relative
            add_file(zf, path, arcname)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="QRemeshify", help="QRemeshify package directory")
    parser.add_argument("--upstream-dir", required=True, help="Directory containing upstream OS ZIP assets")
    parser.add_argument("--version", required=True, help="Release version or tag, e.g. 1.2.0 or v1.2.0")
    parser.add_argument("--output-dir", default="dist", help="Release output directory")
    args = parser.parse_args()

    source_dir = Path(args.source).resolve()
    upstream_dir = Path(args.upstream_dir).resolve()
    output_dir = Path(args.output_dir).resolve()
    version = normalized_version(args.version)

    if not source_dir.is_dir():
        fail(f"source directory does not exist: {source_dir}")
    verify_source_version(source_dir, version)

    assets: dict[str, Path] = {}
    for platform, asset_name in UPSTREAM_ASSET_NAMES.items():
        asset = upstream_dir / asset_name
        if not asset.is_file():
            fail(f"missing upstream {platform} asset: {asset}")
        assets[platform] = asset

    with tempfile.TemporaryDirectory(prefix="reqremeshify-release-") as temp_name:
        temp = Path(temp_name)
        addon_root = temp / "QRemeshify"
        copy_source_tree(source_dir, addon_root)
        lib_dir = addon_root / "lib"
        lib_dir.mkdir(parents=True, exist_ok=True)

        # Include the GPL license inside the distributable package when available.
        repo_license = source_dir.parent / "LICENSE"
        if repo_license.is_file():
            shutil.copy2(repo_license, addon_root / "LICENSE")

        copied: list[str] = []
        for platform, archive in assets.items():
            extracted = temp / f"upstream-{platform}"
            extracted.mkdir()
            safe_extract(archive, extracted)
            for binary_name in EXPECTED_BINARIES[platform]:
                binary = find_binary(extracted, binary_name)
                shutil.copy2(binary, lib_dir / binary_name)
                copied.append(binary_name)

        missing_after_copy = [
            name
            for names in EXPECTED_BINARIES.values()
            for name in names
            if not (lib_dir / name).is_file()
        ]
        if missing_after_copy:
            fail("release package is missing native libraries: " + ", ".join(missing_after_copy))

        output_dir.mkdir(parents=True, exist_ok=True)
        addon_zip = output_dir / f"ReQRemeshify-{version}-Blender4-addon.zip"
        extension_zip = output_dir / f"ReQRemeshify-{version}-Blender4.2-extension.zip"

        # Blender 4.0/4.1 legacy add-on package: QRemeshify/ is the ZIP root folder.
        write_zip(addon_root, addon_zip, nested_folder=True)
        # Blender 4.2+ extension package: blender_manifest.toml must be at ZIP root.
        write_zip(addon_root, extension_zip, nested_folder=False)

        print("Bundled native libraries:")
        for name in copied:
            print(f"  - {name}")
        print("Created release assets:")
        print(f"  - {addon_zip}")
        print(f"  - {extension_zip}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
