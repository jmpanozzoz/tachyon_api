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
    dependencies = message.get_all("Requires-Dist", [])
    require(any(re.match(r"orjson\b.*>=3\.11\.6(?:[,; )]|$)", dep) for dep in dependencies), "missing safe orjson minimum")
    require(not any(re.match(r"cython\b", dep, re.I) for dep in dependencies), "Cython dependency remains")
    return message


def check_wheel(path, version, python_files):
    require(path.name == f"tachyon_api-{version}-py3-none-any.whl", "expected one portable py3-none-any wheel")
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        require(len(names) == len(set(names)), "duplicate archive paths")
        require(all(not PurePosixPath(name).is_absolute() and ".." not in PurePosixPath(name).parts and "\\" not in name for name in names), "unsafe wheel path")
        dist = f"tachyon_api-{version}.dist-info"
        metadata(archive.read(f"{dist}/METADATA"), version)
        wheel = BytesParser().parsebytes(archive.read(f"{dist}/WHEEL"))
        require(set(wheel.get_all("Tag", [])) == {"py3-none-any"}, "WHEEL tags differ from filename")
        require(wheel["Root-Is-Purelib"] == "true", "Root-Is-Purelib differs from wheel type")
        require(python_files <= set(names), "wheel is missing Python modules")
        for name in python_files:
            require(archive.read(name) == (ROOT / name).read_bytes(), f"wheel source differs from checkout: {name}")
        binaries = {name for name in names if name.endswith((".so", ".pyd", ".dylib", ".dll"))}
        require(not binaries, "portable wheel contains native binary files")
        require(not any(name.endswith((".pyx", ".pxd")) for name in names), "wheel contains retired Cython sources")
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
    return "portable"


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
        require({prefix + name for name in required} <= set(names), "sdist is missing build/Python sources")
        for name in source_files | {"setup.py", "pyproject.toml", "MANIFEST.in", "README.md"}:
            require(archive.extractfile(prefix + name).read() == (ROOT / name).read_bytes(), f"sdist source differs from checkout: {name}")
        require(not any(name.endswith((".so", ".pyd", ".dylib", ".dll")) for name in names), "sdist contains stale compiled binaries")
        require(not any(name.endswith((".pyx", ".pxd")) for name in names), "sdist contains retired Cython sources")
        metadata(archive.extractfile(prefix + "PKG-INFO").read(), version)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    python_files = {str(path.relative_to(ROOT)).replace("\\", "/") for path in (ROOT / "tachyon_api").rglob("*.py")}
    source_files = python_files
    try:
        require(args.directory.is_dir(), "artifact directory does not exist")
        files = sorted(path for path in args.directory.iterdir() if path.is_file())
        wheels = [path for path in files if path.suffix == ".whl"]
        sdists = [path for path in files if path.name.endswith(".tar.gz")]
        require(len(sdists) == 1, "release directory must contain exactly one sdist")
        require(len(wheels) == 1, "release directory must contain exactly one portable wheel")
        require(bool(python_files), "Python source inventory is empty")
        check_wheel(wheels[0], args.version, python_files)
        check_sdist(sdists[0], args.version, source_files)
    except (ValueError, KeyError, OSError, tarfile.TarError, zipfile.BadZipFile) as exc:
        parser.exit(1, f"Artifact check failed: {exc}\n")
    print(f"Checked {len(wheels)} wheel(s), one sdist, version {args.version}; Python-only distribution.")
    print("Archive consistency passed. Installation, interpreter compatibility and runtime behavior require separate tests.")


if __name__ == "__main__":
    main()
