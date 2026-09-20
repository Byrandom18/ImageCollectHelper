from __future__ import annotations

import os
import tkinter.filedialog as filedialog
from pathlib import Path

import customtkinter as ctk

from collector.paths import DESTINATIONS, destination_path
from collector.storage import load_settings, save_settings
from renamer.logic import apply_plan, build_plan

ACCENT = "#6ea8fe"


def _enable_dpi() -> None:
    try:
        from ctypes import windll

        windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            from ctypes import windll

            windll.user32.SetProcessDPIAware()
        except Exception:
            pass


class RenamerApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Перенумерация файлов")
        self.geometry("760x620")
        self.minsize(640, 520)
        self.configure(fg_color="#16181d")
        self._settings = load_settings()
        self._build()
        self._load()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(16, 8))
        ctk.CTkLabel(header, text="Сплошная нумерация", font=ctk.CTkFont(size=24, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(
            header,
            text="01, 02, 04.webp → 01, 02, 03.webp. Файлы без числового имени не трогает.",
            text_color="#9aa3b2",
            font=ctk.CTkFont(size=13),
        ).pack(anchor="w", pady=(2, 0))

        body = ctk.CTkFrame(self, fg_color="#1e2128", corner_radius=14)
        body.pack(fill="both", expand=True, padx=16, pady=8)

        dest_row = ctk.CTkFrame(body, fg_color="transparent")
        dest_row.pack(fill="x", padx=14, pady=(14, 8))
        labels = [title for _id, title, _path in DESTINATIONS]
        self.dest_menu = ctk.CTkOptionMenu(dest_row, values=labels, command=self._on_dest, width=240)
        self.dest_menu.pack(side="left")
        ctk.CTkButton(dest_row, text="Папка…", width=90, command=self._browse).pack(side="left", padx=8)
        self.path_entry = ctk.CTkEntry(body, height=36)
        self.path_entry.pack(fill="x", padx=14, pady=(0, 10))

        nums = ctk.CTkFrame(body, fg_color="transparent")
        nums.pack(fill="x", padx=14, pady=(0, 8))
        self.start_var = ctk.StringVar(value="1")
        self.pad_var = ctk.StringVar(value="2")
        self._num_field(nums, "Номер с", self.start_var, 0)
        self._num_field(nums, "Цифр в имени", self.pad_var, 1)
        self.images_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(nums, text="Только картинки", variable=self.images_var).grid(row=0, column=2, padx=16, sticky="s")

        btns = ctk.CTkFrame(body, fg_color="transparent")
        btns.pack(fill="x", padx=14, pady=(4, 8))
        ctk.CTkButton(btns, text="Показать план", width=140, fg_color="#3a3f4b", command=self._preview).pack(side="left")
        ctk.CTkButton(
            btns,
            text="Переименовать",
            width=160,
            fg_color=ACCENT,
            text_color="#102043",
            font=ctk.CTkFont(weight="bold"),
            command=self._rename,
        ).pack(side="left", padx=8)
        ctk.CTkButton(btns, text="Открыть папку", width=130, fg_color="#3a3f4b", command=self._open_folder).pack(side="left")

        self.status = ctk.CTkLabel(body, text="Выберите папку и нажмите «Показать план»", text_color="#c5cad6", anchor="w")
        self.status.pack(fill="x", padx=16, pady=(0, 6))
        self.log = ctk.CTkTextbox(body, font=ctk.CTkFont(family="Consolas", size=13))
        self.log.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        self.log.configure(state="disabled")

    def _num_field(self, parent, label: str, var: ctk.StringVar, column: int) -> None:
        cell = ctk.CTkFrame(parent, fg_color="transparent")
        cell.grid(row=0, column=column, padx=(0, 12), sticky="w")
        ctk.CTkLabel(cell, text=label, text_color="#9aa3b2").pack(anchor="w")
        ctk.CTkEntry(cell, textvariable=var, width=100, height=34).pack(anchor="w")

    def _on_dest(self, label: str) -> None:
        for dest_id, title, path in DESTINATIONS:
            if title == label:
                if dest_id != "custom":
                    self._set_path(path)
                break

    def _set_path(self, path: Path) -> None:
        self.path_entry.delete(0, "end")
        self.path_entry.insert(0, str(path))

    def _browse(self) -> None:
        chosen = filedialog.askdirectory(initialdir=self.path_entry.get() or str(Path.home()))
        if chosen:
            self.dest_menu.set("Своя папка")
            self._set_path(Path(chosen))

    def _open_folder(self) -> None:
        path = Path(self.path_entry.get().strip() or ".")
        path.mkdir(parents=True, exist_ok=True)
        os.startfile(path)  # type: ignore[attr-defined]

    def _int(self, var: ctk.StringVar, default: int, lo: int, hi: int) -> int:
        try:
            value = int(str(var.get()).strip())
        except ValueError:
            return default
        return max(lo, min(hi, value))

    def _plan(self):
        folder = Path(self.path_entry.get().strip())
        if not folder.is_dir():
            raise ValueError(f"Нет такой папки: {folder}")
        return build_plan(
            folder,
            start=self._int(self.start_var, 1, 1, 99999),
            pad_width=self._int(self.pad_var, 2, 1, 6),
            images_only=self.images_var.get(),
        )

    def _write_log(self, lines: list[str]) -> None:
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.insert("end", "\n".join(lines) + ("\n" if lines else ""))
        self.log.configure(state="disabled")

    def _preview(self) -> None:
        try:
            plan = self._plan()
        except ValueError as exc:
            self.status.configure(text=str(exc))
            return
        changed = [item for item in plan if item.changed]
        lines = [f"{item.source.name}  →  {item.dest.name}" for item in plan]
        if not plan:
            self.status.configure(text="Нет файлов с именами вроде 01.webp")
            self._write_log(["В папке нет пронумерованных файлов."])
            return
        self.status.configure(text=f"Файлов: {len(plan)}, переименуется: {len(changed)}")
        self._write_log(lines or ["Все имена уже идут подряд."])

    def _rename(self) -> None:
        try:
            plan = self._plan()
            changed = apply_plan(plan)
        except Exception as exc:
            self.status.configure(text=str(exc))
            self._write_log([str(exc)])
            return
        if not changed:
            self.status.configure(text="Переименовывать нечего — номера уже подряд")
            self._preview()
            return
        self.status.configure(text=f"Готово: переименовано {len(changed)}")
        self._preview()

    def _load(self) -> None:
        dest_id = self._settings.get("dest_id", "campaign")
        title = next((t for i, t, _p in DESTINATIONS if i == dest_id), DESTINATIONS[0][1])
        self.dest_menu.set(title)
        self._set_path(Path(self._settings.get("output_dir") or destination_path(dest_id)))
        self.start_var.set(str(self._settings.get("rename_start", 1)))
        self.pad_var.set(str(self._settings.get("pad_width", 2)))
        self.images_var.set(self._settings.get("rename_images_only", True))

    def _on_close(self) -> None:
        data = dict(self._settings)
        data["output_dir"] = self.path_entry.get().strip()
        data["rename_start"] = self._int(self.start_var, 1, 1, 99999)
        data["pad_width"] = self._int(self.pad_var, 2, 1, 6)
        data["rename_images_only"] = self.images_var.get()
        try:
            save_settings(data)
        except Exception:
            pass
        self.destroy()


def run_gui() -> None:
    _enable_dpi()
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    RenamerApp().mainloop()
