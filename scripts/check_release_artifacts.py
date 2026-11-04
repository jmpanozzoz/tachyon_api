"""Check local release archive consistency; does not install or publish artifacts."""
from __future__ import annotations

import argparse
import base64
import csv
from email.parser import BytesParser
import hashlib
import io
from pathlib import Path, PurePosixPath
import re
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def metadata(data, version):
    message = BytesParser().parsebytes(data)
    require(message["Name"] == "tachyon-api", "unexpected distribution name")
    require(message["Version"] == version, "metadata version differs from requested release")
    requires = message["Requires-Python"]
    require(requires is not None and set(requires.replace(" ", "").split(",")) == {">=3.10", "<3.14"},
            f"unexpected supported Python constraint: {requires}")
    return message


def check_wheel(path, version, python_files, native_modules, native_platform):
    match = re.fullmatch(r"tachyon_api-(.+?)-(py3|cp31[0-3])-(none|cp31[0-3])-(.+)\.whl", path.name)
    require(match is not None, f"unexpected wheel filename: {path.name}")
    found_version, python, abi, platform = match.groups()
    require(found_version == version, "wheel filename version mismatch")
    portable = platform == "any"
    require((python == "py3" and abi == "none") if portable else (python == abi and python.startswith("cp")),
            "wheel interpreter/ABI tags do not match release policy")
    if native_platform and not portable:
        require(platform == native_platform, f"unexpected native platform: {platform}")
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        require(len(names) == len(set(names)), "duplicate archive paths")
        require(all(not PurePosixPath(name).is_absolute() and ".." not in PurePosixPath(name).parts and "\\" not in name for name in names), "unsafe wheel path")
        dist = f"tachyon_api-{version}.dist-info"
        metadata(archive.read(f"{dist}/METADATA"), version)
        wheel = BytesParser().parsebytes(archive.read(f"{dist}/WHEEL"))
        require(set(wheel.get_all("Tag", [])) == {f"{python}-{abi}-{platform}"}, "WHEEL tags differ from filename")
        require(wheel["Root-Is-Purelib"] == str(portable).lower(), "Root-Is-Purelib differs from wheel type")
        require(python_files <= set(names), "wheel is missing Python fallback modules")
        binaries = {name for name in names if name.endswith((".so", ".pyd", ".dylib", ".dll"))}
        if portable:
            require(not binaries, "portable wheel contains native binary files")
        else:
            for module in native_modules:
                candidates = [name for name in binaries if name.startswith(module + ".")]
                require(len(candidates) == 1, f"missing/duplicate native extension: {module}")
        record_name = f"{dist}/RECORD"
        records = list(csv.reader(io.StringIO(archive.read(record_name).decode())))
        require({row[0] for row in records} == set(names), "RECORD does not cover archive contents")
        require(len(records) == len(names), "duplicate RECORD entries")
        for name, digest, size in records:
            if name == record_name:
                require(not digest and not size, "RECORD must not hash itself")
                continue
            require(digest.startswith("sha256="), f"missing SHA256 RECORD digest: {name}")
            content = archive.read(name)
            actual = base64.urlsafe_b64encode(hashlib.sha256(content).digest()).rstrip(b"=").decode()
            require(digest == f"sha256={actual}" and size == str(len(content)), f"RECORD mismatch: {name}")
        entries = archive.read(f"{dist}/entry_points.txt").decode()
        require("tachyon" in entries and "tachyon_api.cli:app" in entries, "CLI entry point missing")
    return "portable" if portable else "native"


def check_sdist(path, version, source_files):
    require(path.name == f"tachyon_api-{version}.tar.gz", "unexpected sdist filename")
    with tarfile.open(path, "r:gz") as archive:
        members = archive.getmembers()
        names = [member.name for member in members]
        require(len(names) == len(set(names)), "duplicate sdist paths")
        require(all(not PurePosixPath(name).is_absolute() and ".." not in PurePosixPath(name).parts and "\\" not in name for name in names), "unsafe sdist path")
        require(all(not member.issym() and not member.islnk() for member in members), "sdist contains links")
        prefix = f"tachyon_api-{version}/"
        require(all(name == prefix[:-1] or name.startswith(prefix) for name in names), "sdist has inconsistent root directory")
        required = source_files | {"setup.py", "pyproject.toml", "MANIFEST.in", "README.md", "LICENSE", "PKG-INFO"}
        require({prefix + name for name in required} <= set(names), "sdist is missing build/Python/Cython sources")
        require(not any(name.endswith((".so", ".pyd", ".dylib", ".dll")) for name in names), "sdist contains stale compiled binaries")
        metadata(archive.extractfile(prefix + "PKG-INFO").read(), version)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--version", required=True)
    parser.add_argument("--require-native", action="store_true")
    parser.add_argument("--native-platform", help="Exact native platform tag, for example macosx_11_0_arm64")
    args = parser.parse_args()
    python_files = {str(path.relative_to(ROOT)).replace("\\", "/") for path in (ROOT / "tachyon_api").rglob("*.py")}
    native_modules = {str(path.relative_to(ROOT).with_suffix("")).replace("\\", "/") for path in (ROOT / "tachyon_api").rglob("*.pyx")}
    source_files = python_files | {str(path.relative_to(ROOT)).replace("\\", "/") for pattern in ("*.pyx", "*.pxd") for path in (ROOT / "tachyon_api").rglob(pattern)}
    try:
        require(args.directory.is_dir(), "artifact directory does not exist")
        files = sorted(path for path in args.directory.iterdir() if path.is_file())
        wheels = [path for path in files if path.suffix == ".whl"]
        sdists = [path for path in files if path.name.endswith(".tar.gz")]
        require(len(sdists) == 1, "release directory must contain exactly one sdist")
        kinds = [check_wheel(path, args.version, python_files, native_modules, args.native_platform) for path in wheels]
        require(kinds.count("portable") == 1, "release directory must contain exactly one portable wheel")
        require(not args.require_native or "native" in kinds, "release directory has no native wheel")
        check_sdist(sdists[0], args.version, source_files)
    except (ValueError, KeyError, OSError, tarfile.TarError, zipfile.BadZipFile) as exc:
        parser.exit(1, f"Artifact check failed: {exc}\n")
    print(f"Checked {len(wheels)} wheel(s), one sdist, version {args.version}; {len(native_modules)} native module sources.")
    print("Archive consistency passed. Installation, interpreter compatibility and runtime behavior require separate tests.")


if __name__ == "__main__":
    main()
