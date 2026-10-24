"""Find workspace files and safely inspect or extract ZIP/TAR archives."""

from __future__ import annotations

import argparse
import ntpath
import shutil
import stat
import sys
import tarfile
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


ARCHIVE_SUFFIXES = (
    ".tar.gz",
    ".tar.bz2",
    ".tar.xz",
    ".tgz",
    ".tbz2",
    ".txz",
    ".tar",
    ".zip",
)


@dataclass(frozen=True)
class ArchiveEntry:
    name: str
    is_directory: bool
    size: int


def is_archive(path: Path) -> bool:
    return path.name.casefold().endswith(ARCHIVE_SUFFIXES)


def archive_output_name(path: Path) -> str:
    name = path.name
    folded = name.casefold()
    for suffix in ARCHIVE_SUFFIXES:
        if folded.endswith(suffix):
            return name[: -len(suffix)] or "extracted"
    return path.stem or "extracted"


def _safe_member_path(name: str, output_dir: Path) -> tuple[PurePosixPath, bool]:
    if not name or "\\" in name or ntpath.splitdrive(name)[0]:
        raise ValueError(f"Ungültiger Archivpfad: {name!r}")

    member_path = PurePosixPath(name)
    if member_path.is_absolute() or ".." in member_path.parts:
        raise ValueError(f"Archivpfad verlässt das Zielverzeichnis: {name!r}")

    is_directory = name.endswith("/") or name.endswith("\\")
    if not member_path.parts:
        if is_directory:
            return member_path, True
        raise ValueError(f"Ungültiger Archivpfad: {name!r}")

    resolved = output_dir.joinpath(*member_path.parts).resolve()
    if not resolved.is_relative_to(output_dir.resolve()):
        raise ValueError(f"Archivpfad verlässt das Zielverzeichnis: {name!r}")
    return member_path, is_directory


def _validate_entries(entries: list[ArchiveEntry], output_dir: Path) -> None:
    seen: dict[PurePosixPath, bool] = {}
    for entry in entries:
        member_path, trailing_directory = _safe_member_path(entry.name, output_dir)
        if not member_path.parts:
            continue
        is_directory = entry.is_directory or trailing_directory
        if member_path in seen:
            raise ValueError(f"Doppelter Archivpfad: {entry.name!r}")

        for parent in member_path.parents:
            if parent != PurePosixPath(".") and seen.get(parent) is False:
                raise ValueError(f"Datei wird als Verzeichnis verwendet: {str(parent)!r}")
        if not is_directory and any(existing.is_relative_to(member_path) for existing in seen):
            raise ValueError(f"Datei kollidiert mit einem untergeordneten Pfad: {entry.name!r}")
        seen[member_path] = is_directory


def inspect_archive(path: Path, output_dir: Path) -> list[ArchiveEntry]:
    entries: list[ArchiveEntry] = []
    if path.name.casefold().endswith(".zip"):
        with zipfile.ZipFile(path) as archive:
            for item in archive.infolist():
                mode = item.external_attr >> 16
                file_type = stat.S_IFMT(mode)
                if file_type == stat.S_IFLNK or file_type not in (0, stat.S_IFREG, stat.S_IFDIR):
                    raise ValueError(f"Nicht unterstützter Dateityp im Archiv: {item.filename!r}")
                is_directory = item.is_dir() or file_type == stat.S_IFDIR
                entries.append(ArchiveEntry(item.filename, is_directory, item.file_size))
    else:
        with tarfile.open(path, mode="r:*") as archive:
            for item in archive.getmembers():
                if not (item.isdir() or item.isfile()):
                    raise ValueError(f"Nicht unterstützter Dateityp im Archiv: {item.name!r}")
                entries.append(ArchiveEntry(item.name, item.isdir(), item.size))

    _validate_entries(entries, output_dir)
    return entries


def find_files(root: Path, query: str, search_content: bool) -> list[Path]:
    normalized_query = query.casefold()
    matches = []
    for path in root.rglob("*"):
        if path.is_symlink() or not path.is_file():
            continue
        relative_path = path.relative_to(root).as_posix()
        if normalized_query in relative_path.casefold():
            matches.append(path)
            continue
        if search_content and not is_archive(path):
            try:
                if normalized_query in path.read_text(encoding="utf-8").casefold():
                    matches.append(path)
            except (OSError, UnicodeError):
                continue
    return sorted(matches)


def extract_archive(path: Path, destination: Path, entries: list[ArchiveEntry]) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    output_dir = destination / archive_output_name(path)
    output_dir.mkdir()
    resolved_output_dir = output_dir.resolve()

    try:
        if path.name.casefold().endswith(".zip"):
            with zipfile.ZipFile(path) as archive:
                for entry in entries:
                    member_path, _ = _safe_member_path(entry.name, resolved_output_dir)
                    if not member_path.parts:
                        continue
                    target = resolved_output_dir.joinpath(*member_path.parts)
                    if entry.is_directory:
                        target.mkdir(parents=True, exist_ok=True)
                    else:
                        target.parent.mkdir(parents=True, exist_ok=True)
                        with archive.open(entry.name) as source, target.open("xb") as output:
                            shutil.copyfileobj(source, output)
        else:
            with tarfile.open(path, mode="r:*") as archive:
                for entry in entries:
                    member_path, _ = _safe_member_path(entry.name, resolved_output_dir)
                    if not member_path.parts:
                        continue
                    target = resolved_output_dir.joinpath(*member_path.parts)
                    if entry.is_directory:
                        target.mkdir(parents=True, exist_ok=True)
                    else:
                        target.parent.mkdir(parents=True, exist_ok=True)
                        source = archive.extractfile(entry.name)
                        if source is None:
                            raise ValueError(f"Archivdatei kann nicht gelesen werden: {entry.name!r}")
                        with source, target.open("xb") as output:
                            shutil.copyfileobj(source, output)
    except Exception:
        shutil.rmtree(output_dir)
        raise
    return output_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Dateien finden und ZIP/TAR-Archive sicher prüfen oder entpacken."
    )
    parser.add_argument("query", help="Suchtext für Dateipfade und optional Dateiinhalte")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Suchwurzel (Standard: aktuelles Verzeichnis)")
    parser.add_argument("--content", action="store_true", help="Textdateien zusätzlich nach Inhalt durchsuchen")
    parser.add_argument("--extract", action="store_true", help="Gefundene Archive nach der Vorschau entpacken")
    parser.add_argument("--destination", type=Path, help="Zielordner; je Archiv wird ein neuer Unterordner angelegt")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.extract and args.destination is None:
        parser.error("--destination ist beim Entpacken erforderlich.")
    try:
        root = args.root.resolve(strict=True)
    except OSError as error:
        parser.error(f"Suchwurzel ist nicht verfügbar: {error}")
    if not root.is_dir():
        parser.error(f"Suchwurzel ist kein Verzeichnis: {root}")

    matches = find_files(root, args.query, args.content)
    if not matches:
        print("Keine passenden Dateien gefunden.")
        return 0

    archives = [path for path in matches if is_archive(path)]
    print("Passende Dateien:")
    for path in matches:
        print(f"- {path.relative_to(root)}")

    inspected: list[tuple[Path, list[ArchiveEntry]]] = []
    failed = False
    for path in archives:
        output_dir = (args.destination or root) / archive_output_name(path)
        try:
            entries = inspect_archive(path, output_dir)
        except (OSError, tarfile.TarError, zipfile.BadZipFile, ValueError) as error:
            print(f"Übersprungen: {path.relative_to(root)} ({error})", file=sys.stderr)
            failed = True
            continue
        inspected.append((path, entries))
        print(f"\nInhalt von {path.relative_to(root)}:")
        if entries:
            for entry in entries:
                print(f"  {'[Ordner]' if entry.is_directory else '[Datei]'} {entry.name}")
        else:
            print("  (leer)")

    if args.extract:
        destination = args.destination.resolve()
        for path, entries in inspected:
            try:
                output_dir = extract_archive(path, destination, entries)
            except (OSError, tarfile.TarError, zipfile.BadZipFile, ValueError) as error:
                print(f"Nicht entpackt: {path.relative_to(root)} ({error})", file=sys.stderr)
                failed = True
            else:
                print(f"Entpackt nach: {output_dir}")
    elif inspected:
        print("\nVorschau. Zum Entpacken --extract und --destination angeben.")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())