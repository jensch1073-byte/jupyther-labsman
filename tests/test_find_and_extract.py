import tempfile
import sys
import unittest
import zipfile
from pathlib import Path

from find_and_extract import extract_archive, inspect_archive
from jupyter_lab_manager import jupyter_command


class ArchiveExtractionTests(unittest.TestCase):
    def test_extracts_files_into_a_new_archive_folder(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            archive_path = root / "bundle.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("nested/data.txt", "hello")

            output_dir = root / "output" / "bundle"
            entries = inspect_archive(archive_path, output_dir)
            extracted = extract_archive(archive_path, output_dir.parent, entries)

            self.assertEqual((extracted / "nested" / "data.txt").read_text(), "hello")

    def test_rejects_paths_outside_the_extraction_directory(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            archive_path = root / "unsafe.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("../outside.txt", "no")

            with self.assertRaisesRegex(ValueError, "verlässt das Zielverzeichnis"):
                inspect_archive(archive_path, root / "output")

    def test_refuses_to_overwrite_an_existing_archive_folder(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            archive_path = root / "bundle.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("data.txt", "new")
            output_dir = root / "output" / "bundle"
            output_dir.mkdir(parents=True)
            existing_file = output_dir / "keep.txt"
            existing_file.write_text("existing")

            entries = inspect_archive(archive_path, output_dir)
            with self.assertRaises(FileExistsError):
                extract_archive(archive_path, output_dir.parent, entries)

            self.assertEqual(existing_file.read_text(), "existing")


class JupyterCommandTests(unittest.TestCase):
    def test_command_uses_current_python_and_selected_port(self):
        command = jupyter_command(8899)

        self.assertEqual(command[0], sys.executable)
        self.assertIn("jupyter", command)
        self.assertIn("lab", command)
        self.assertIn("--ServerApp.port=8899", command)


if __name__ == "__main__":
    unittest.main()