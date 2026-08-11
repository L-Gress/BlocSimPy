"""Owns the current Project Folder.

Everything the app persists to disk -- Diagrams, saved SubGraphs, and
Scripts -- lives directly in one flat, user-chosen folder: no imposed
subfolder structure, so you can point BlocSimPy at any folder anywhere on
disk. File > Open Project Folder... switches folders without restarting.
No project is opened automatically -- BlocSimPy starts with none open
every launch (same as diagrams starting with none open), and User Space
stays empty until you explicitly choose one.
"""
import os
import shutil
from PySide6.QtWidgets import QFileDialog, QMessageBox


class ProjectManager:
    """Resolves, switches, and persists the current project root."""

    # Earlier versions organized a project into these two subfolders
    # (each itself nested one folder deep). The current layout is flat --
    # no subfolders at all -- so _set_root() flattens and removes these
    # the first time it sees them again.
    _LEGACY_SUBFOLDERS = ("user_library", "user_scripts")

    def __init__(self, main_window):
        self.main_window = main_window
        self.project_root = None

    @property
    def project_name(self):
        return os.path.basename(os.path.normpath(self.project_root)) if self.project_root else ""

    def open_project_dialog(self):
        """File > Open Project Folder... -- switch to (or, at startup,
        first open) a project. Refuses to switch out from under any open
        diagram's unsaved changes (not just the active one)."""
        if not self.main_window.confirm_discard_all_diagrams():
            return

        path = QFileDialog.getExistingDirectory(
            self.main_window, "Open Project Folder", self.project_root or os.getcwd()
        )
        if not path:
            return

        self._set_root(path)
        # A different project means a different set of diagrams/SubGraphs/
        # scripts -- none of the previously open diagrams (if any) belong
        # here. confirm_discard_all_diagrams() above already handled
        # unsaved changes, so this closes them without asking again, and
        # without opening a replacement blank one -- same "don't open
        # something the user didn't ask for" rule diagrams start under.
        self.main_window.close_all_diagrams()

    def _set_root(self, path):
        os.makedirs(path, exist_ok=True)
        self._migrate_legacy_layout(path)

        self.project_root = path

        user_space = getattr(self.main_window, "user_space_widget", None)
        if user_space is not None:
            user_space.set_root(path)

        if hasattr(self.main_window, "refresh_title"):
            self.main_window.refresh_title()

    def _migrate_legacy_layout(self, root):
        """One-time cleanup for a project root laid out by an earlier
        BlocSimPy version. Flattens anything found in user_library/ or
        user_scripts/ up into `root` and removes those folders. Cheap
        no-op once migrated, since they won't exist anymore."""
        migrated = []
        for legacy_name in self._LEGACY_SUBFOLDERS:
            legacy_dir = os.path.join(root, legacy_name)
            if not os.path.isdir(legacy_dir):
                continue
            migrated.extend(self._flatten_into(legacy_dir, root))
            shutil.rmtree(legacy_dir, ignore_errors=True)

        if migrated:
            QMessageBox.information(
                self.main_window, "Project Folder Updated",
                f"'{root}' used the older user_library/user_scripts layout. "
                f"Moved {len(migrated)} file(s) directly into the project "
                "folder and removed those subfolders:\n\n" + "\n".join(sorted(migrated))
            )

    def _flatten_into(self, src_dir, dest_dir):
        """Move every file under src_dir (recursing into any nested
        subfolders) directly into dest_dir, renaming on collision instead
        of overwriting. Returns the list of resulting filenames."""
        moved = []
        for entry in os.listdir(src_dir):
            path = os.path.join(src_dir, entry)
            if os.path.isdir(path):
                moved.extend(self._flatten_into(path, dest_dir))
            else:
                dest_path = self._unique_path(os.path.join(dest_dir, entry))
                shutil.move(path, dest_path)
                moved.append(os.path.basename(dest_path))
        return moved

    @staticmethod
    def _unique_path(path):
        """Avoid clobbering an existing file of the same name at the
        destination -- append ' (2)', ' (3)', ... before the extension."""
        if not os.path.exists(path):
            return path
        base, ext = os.path.splitext(path)
        n = 2
        while os.path.exists(f"{base} ({n}){ext}"):
            n += 1
        return f"{base} ({n}){ext}"
