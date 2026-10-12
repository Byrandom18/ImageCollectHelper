from __future__ import annotations

import ctypes
import shutil
from ctypes import wintypes
from pathlib import Path

FO_DELETE = 3
FOF_SILENT = 0x0004
FOF_NOCONFIRMATION = 0x0010
FOF_ALLOWUNDO = 0x0040
FOF_NOERRORUI = 0x0400


class _ShFileOp(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("wFunc", ctypes.c_uint),
        ("pFrom", ctypes.c_wchar_p),
        ("pTo", ctypes.c_wchar_p),
        ("fFlags", ctypes.c_ushort),
        ("fAnyOperationsAborted", wintypes.BOOL),
        ("hNameMappings", ctypes.c_void_p),
        ("lpszProgressTitle", ctypes.c_wchar_p),
    ]


def meta_path(path: Path) -> Path:
    return Path(str(path) + ".meta")


def move_image_to(source: Path, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if source.resolve() == dest.resolve():
        return dest
    meta = meta_path(source)
    shutil.move(str(source), str(dest))
    if meta.is_file():
        meta_dest = meta_path(dest)
        if meta_dest.exists():
            meta_dest.unlink()
        shutil.move(str(meta), str(meta_dest))
    return dest


def move_image(source: Path, folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    if source.parent.resolve() == folder.resolve():
        raise ValueError("папка назначения совпадает с исходной")
    dest = _unique(folder, source.name)
    meta = meta_path(source)
    shutil.move(str(source), str(dest))
    if meta.is_file():
        shutil.move(str(meta), str(meta_path(dest)))
    return dest


def recycle_image(source: Path) -> None:
    paths = [source]
    meta = meta_path(source)
    if meta.is_file():
        paths.append(meta)
    try:
        _recycle(paths)
    except OSError:
        for path in paths:
            if path.exists():
                path.unlink()
    missing = [path.name for path in paths if path.exists()]
    if missing:
        raise OSError("не удалось удалить " + ", ".join(missing))


def _unique(folder: Path, name: str) -> Path:
    dest = folder / name
    if not dest.exists():
        return dest
    stem = Path(name).stem
    suffix = Path(name).suffix
    number = 2
    while True:
        dest = folder / f"{stem}_{number}{suffix}"
        if not dest.exists():
            return dest
        number += 1


def _recycle(paths: list[Path]) -> None:
    raw = "\0".join(str(path.resolve()) for path in paths) + "\0"
    buffer = ctypes.create_unicode_buffer(raw)
    operation = _ShFileOp()
    operation.wFunc = FO_DELETE
    operation.pFrom = ctypes.cast(buffer, ctypes.c_wchar_p)
    operation.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT | FOF_NOERRORUI
    error = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(operation))
    if error != 0 or operation.fAnyOperationsAborted:
        raise OSError(error or "отменено")
