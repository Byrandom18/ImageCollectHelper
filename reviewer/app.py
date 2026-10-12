from __future__ import annotations

import threading
import time
import tkinter.filedialog as filedialog
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk
from PIL import Image, ImageOps

from collector.paths import DESTINATIONS
from collector.storage import load_settings, save_settings
from reviewer.actions import move_image, move_image_to, recycle_image
from reviewer.difficulty import Recommendation, recommend_file
from reviewer.score import Analysis, analyze_file, list_images, paint_grid

ACCENT = "#6ea8fe"
PRESET_TITLES = [title for _item_id, title, _path in DESTINATIONS]


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


class ReviewerApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Отбор картинок")
        self.geometry("1280x860")
        self.minsize(980, 680)
        self.configure(fg_color="#16181d")
        self._settings = load_settings()
        self._queue: list[Path] = []
        self._index = 0
        self._cache: dict[tuple, Analysis] = {}
        self._ranks: dict[tuple, Recommendation] = {}
        self._photo = None
        self._generation = 0
        self._scanning = False
        self._lock_until = 0.0
        self._fit = (0, 0)
        self._resize_job = None
        self._build()
        self._load()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build(self) -> None:
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=12, pady=12)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        left = ctk.CTkScrollableFrame(body, width=320, fg_color="#1e2128", corner_radius=14)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        stage_wrap = ctk.CTkFrame(body, fg_color="#1e2128", corner_radius=14)
        stage_wrap.grid(row=0, column=1, sticky="nsew")

        ctk.CTkLabel(left, text="Откуда", font=ctk.CTkFont(size=15, weight="bold"), text_color=ACCENT).pack(
            anchor="w", padx=12, pady=(12, 6)
        )
        self.source_menu = ctk.CTkOptionMenu(left, values=PRESET_TITLES, command=self._on_source_preset, width=280)
        self.source_menu.pack(anchor="w", padx=12)
        source_row = ctk.CTkFrame(left, fg_color="transparent")
        source_row.pack(fill="x", padx=12, pady=8)
        self.source_entry = ctk.CTkEntry(source_row, height=34)
        self.source_entry.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(source_row, text="…", width=36, command=self._browse_source).pack(side="left", padx=(6, 0))

        ctk.CTkLabel(left, text="Куда переносить", font=ctk.CTkFont(size=15, weight="bold"), text_color=ACCENT).pack(
            anchor="w", padx=12, pady=(8, 6)
        )
        self.target_menu = ctk.CTkOptionMenu(left, values=PRESET_TITLES, command=self._on_target_preset, width=280)
        self.target_menu.pack(anchor="w", padx=12)
        target_row = ctk.CTkFrame(left, fg_color="transparent")
        target_row.pack(fill="x", padx=12, pady=8)
        self.target_entry = ctk.CTkEntry(target_row, height=34)
        self.target_entry.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(target_row, text="…", width=36, command=self._browse_target).pack(side="left", padx=(6, 0))

        ctk.CTkLabel(left, text="Сетка пазла", font=ctk.CTkFont(size=15, weight="bold"), text_color=ACCENT).pack(
            anchor="w", padx=12, pady=(8, 6)
        )
        nums = ctk.CTkFrame(left, fg_color="transparent")
        nums.pack(fill="x", padx=12)
        self.cols_var = ctk.StringVar(value="8")
        self.rows_var = ctk.StringVar(value="6")
        self.limit_var = ctk.StringVar(value="4")
        self._num(nums, "Столбцы", self.cols_var, 0)
        self._num(nums, "Строки", self.rows_var, 1)
        self._num(nums, "Макс. похожих", self.limit_var, 2)
        ctk.CTkLabel(
            left,
            text="Одинаковые ячейки — небо, трава, стена. Если их больше порога, на этой сетке пазл тяжёлый. «Разложить по сеткам» отправит такой кадр на более крупную сетку.",
            text_color="#8b93a7",
            font=ctk.CTkFont(size=12),
            wraplength=290,
            justify="left",
        ).pack(anchor="w", padx=12, pady=(8, 8))

        self.grid_var = ctk.BooleanVar(value=True)
        self.only_bad_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(left, text="Показывать сетку и одинаковые ячейки", variable=self.grid_var, command=self._show_current).pack(
            anchor="w", padx=12, pady=3
        )
        ctk.CTkCheckBox(
            left,
            text="Показывать только проблемные",
            variable=self.only_bad_var,
            command=self._reload,
        ).pack(anchor="w", padx=12, pady=3)

        ctk.CTkButton(left, text="Открыть папку", height=36, command=self._reload).pack(fill="x", padx=12, pady=(12, 6))
        ctk.CTkButton(
            left,
            text="Перенести подходящие",
            height=36,
            fg_color=ACCENT,
            text_color="#102043",
            font=ctk.CTkFont(weight="bold"),
            command=self._move_good,
        ).pack(fill="x", padx=12, pady=(0, 6))
        ctk.CTkButton(left, text="Разложить по сеткам", height=36, fg_color="#3a3f4b", command=self._spread).pack(
            fill="x", padx=12, pady=(0, 8)
        )
        self.progress = ctk.CTkProgressBar(left, height=8)
        self.progress.pack(fill="x", padx=12, pady=(0, 8))
        self.progress.set(0)
        self.status = ctk.CTkLabel(left, text="Выберите папку и откройте её", text_color="#c5cad6", wraplength=290, justify="left")
        self.status.pack(anchor="w", padx=12, pady=(0, 12))

        self.hint = ctk.CTkLabel(
            stage_wrap,
            text="Левая кнопка — перенести    Правая — в корзину",
            text_color="#9aa3b2",
        )
        self.hint.pack(fill="x", padx=16, pady=(12, 0))
        self.stage = ctk.CTkFrame(stage_wrap, fg_color="#14161b", corner_radius=12)
        self.stage.pack(fill="both", expand=True, padx=12, pady=12)
        self.preview = ctk.CTkLabel(self.stage, text="Здесь будет крупное изображение", text_color="#7b8494")
        self.preview.place(relx=0.5, rely=0.5, anchor="center")
        self.stage.bind("<Configure>", self._on_stage_resize)
        self._hook_clicks(self.preview)

    def _num(self, parent, label: str, var: ctk.StringVar, column: int) -> None:
        cell = ctk.CTkFrame(parent, fg_color="transparent")
        cell.grid(row=0, column=column, padx=(0, 8), sticky="w")
        ctk.CTkLabel(cell, text=label, text_color="#9aa3b2").pack(anchor="w")
        entry = ctk.CTkEntry(cell, textvariable=var, width=84, height=32)
        entry.pack(anchor="w")
        var.trace_add("write", lambda *_: self._schedule_show())

    def _hook_clicks(self, widget) -> None:
        widget.bind("<Button-1>", self._on_left)
        widget.bind("<Button-3>", self._on_right)
        widget.bind("<Double-Button-1>", lambda _event: "break")
        widget.bind("<Double-Button-3>", lambda _event: "break")
        for child in widget.winfo_children():
            self._hook_clicks(child)

    def _on_stage_resize(self, _event) -> None:
        self._schedule_show()

    def _schedule_show(self) -> None:
        if self._resize_job is not None:
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(160, self._show_current)

    def _on_source_preset(self, label: str) -> None:
        path = _preset_path(label)
        if path is not None and label != "Своя папка":
            self._set_entry(self.source_entry, path)

    def _on_target_preset(self, label: str) -> None:
        path = _preset_path(label)
        if path is not None and label != "Своя папка":
            self._set_entry(self.target_entry, path)

    def _browse_source(self) -> None:
        self._browse(self.source_entry, self.source_menu)

    def _browse_target(self) -> None:
        self._browse(self.target_entry, self.target_menu)

    def _browse(self, entry: ctk.CTkEntry, menu: ctk.CTkOptionMenu) -> None:
        chosen = filedialog.askdirectory(initialdir=entry.get() or str(Path.home()))
        if not chosen:
            return
        menu.set("Своя папка")
        self._set_entry(entry, Path(chosen))

    def _set_entry(self, entry: ctk.CTkEntry, path: Path) -> None:
        entry.delete(0, "end")
        entry.insert(0, str(path))

    def _source(self) -> Path:
        return Path(self.source_entry.get().strip())

    def _target(self) -> Path:
        return Path(self.target_entry.get().strip())

    def _cols(self) -> int:
        return _parse(self.cols_var, 8, 2, 20)

    def _rows(self) -> int:
        return _parse(self.rows_var, 6, 2, 20)

    def _limit(self) -> int:
        return _parse(self.limit_var, 4, 1, 200)

    def _reload(self) -> None:
        folder = self._source()
        if not folder.is_dir():
            self.status.configure(text="Нет такой папки с картинками")
            return
        files = list_images(folder)
        self._generation += 1
        self._scanning = False
        self._index = 0
        if not files:
            self._queue = []
            self._show_empty("В папке нет изображений")
            return
        if self.only_bad_var.get():
            self._start_scan(files, mode="filter")
            return
        self._queue = files
        self.status.configure(text=f"{len(files)} изображений")
        self._show_current()

    def _move_good(self) -> None:
        folder = self._source()
        target = self._target()
        if not folder.is_dir():
            self.status.configure(text="Нет такой папки с картинками")
            return
        if not self.target_entry.get().strip():
            self.status.configure(text="Выберите папку, куда переносить")
            return
        if folder.resolve() == target.resolve():
            self.status.configure(text="Папка назначения совпадает с исходной")
            return
        files = list_images(folder)
        if not files:
            self._show_empty("В папке нет изображений")
            return
        agreed = messagebox.askyesno(
            "Перенести подходящие",
            "Проверить сетку и перенести в выбранную папку все картинки без крупных одинаковых ячеек?",
            parent=self,
        )
        if not agreed:
            return
        self._start_scan(files, mode="move")

    def _start_scan(self, files: list[Path], mode: str) -> None:
        self._scanning = True
        self._generation += 1
        generation = self._generation
        cols, rows, limit = self._cols(), self._rows(), self._limit()
        self.progress.set(0)
        self.status.configure(text=f"Проверка 0/{len(files)}")

        def work() -> None:
            good: list[Path] = []
            bad: list[Path] = []
            for index, path in enumerate(files, start=1):
                if generation != self._generation:
                    return
                result = analyze_file(path, cols, rows, limit)
                self._cache[_cache_key(path, cols, rows, limit)] = result
                if result.ok:
                    good.append(path)
                else:
                    bad.append(path)
                self.after(0, lambda done=index, total=len(files), token=generation: self._scan_progress(done, total, token))
            self.after(0, lambda: self._scan_finished(mode, good, bad, generation))

        threading.Thread(target=work, daemon=True).start()

    def _scan_progress(self, done: int, total: int, generation: int) -> None:
        if generation != self._generation:
            return
        self.progress.set(done / total)
        self.status.configure(text=f"Проверка {done}/{total}")

    def _scan_finished(self, mode: str, good: list[Path], bad: list[Path], generation: int) -> None:
        if generation != self._generation:
            return
        self._scanning = False
        self.progress.set(1)
        if mode == "move":
            moved = 0
            target = self._target()
            for path in good:
                if not path.exists():
                    continue
                try:
                    move_image(path, target)
                    moved += 1
                except Exception as exc:
                    self.status.configure(text=str(exc))
                    break
            self._queue = [path for path in bad if path.exists()]
            self._index = 0
            self.status.configure(text=f"Перенесено подходящих: {moved}. Осталось проблемных: {len(self._queue)}")
            self._show_current()
            return
        self._queue = bad
        self._index = 0
        self.status.configure(text=f"Проблемных {len(bad)} из {len(good) + len(bad)}")
        self._show_current()

    def _show_current(self) -> None:
        self._resize_job = None
        if self._scanning:
            return
        if not self._queue:
            self._photo = None
            self.preview.configure(image=None, text="Больше нет изображений")
            return
        self._index = max(0, min(self._index, len(self._queue) - 1))
        path = self._queue[self._index]
        if not path.exists():
            self._queue.pop(self._index)
            self._show_current()
            return
        fit = self._stage_size()
        if fit[0] < 80 or fit[1] < 80:
            self.after(80, self._show_current)
            return
        cols, rows, limit = self._cols(), self._rows(), self._limit()
        key = _cache_key(path, cols, rows, limit)
        analysis = self._cache.get(key)
        if analysis is None:
            analysis = analyze_file(path, cols, rows, limit)
            self._cache[key] = analysis
        try:
            image = self._load_preview(path, fit, analysis)
        except Exception as exc:
            self.preview.configure(image=None, text=str(exc))
            self._hook_clicks(self.preview)
            self.status.configure(text=f"{self._index + 1}/{len(self._queue)}  {path.name}  не открывается")
            return
        self._fit = fit
        self._photo = ctk.CTkImage(light_image=image, dark_image=image, size=image.size)
        self.preview.configure(image=self._photo, text="")
        self._hook_clicks(self.preview)
        advice = self._advice(path)
        color = "#8fd19a" if advice.fits else "#f0a0a0"
        self.status.configure(
            text=f"{self._index + 1}/{len(self._queue)}  {path.name}\n{analysis.summary}\n{advice.summary}",
            text_color=color,
        )

    def _advice(self, path: Path) -> Recommendation:
        try:
            stamp = path.stat().st_mtime_ns
        except OSError:
            stamp = 0
        key = (str(path), stamp, self._limit())
        advice = self._ranks.get(key)
        if advice is None:
            advice = recommend_file(path, self._limit())
            self._ranks[key] = advice
        return advice

    def _spread(self) -> None:
        folder = self._source()
        target = self._target()
        if not folder.is_dir():
            self.status.configure(text="Нет такой папки с картинками")
            return
        if not self.target_entry.get().strip():
            self.status.configure(text="Выберите папку, куда раскладывать")
            return
        files = list_images(folder)
        if not files:
            self._show_empty("В папке нет изображений")
            return
        agreed = messagebox.askyesno(
            "Разложить по сеткам",
            "Проверить каждую картинку на сетках от 3×2 до 10×8.\n"
            "Если на мелкой сетке много одинаковых ячеек, файл уйдёт в папку более крупной сетки.\n"
            "Внутри папки номера идут от более простых к более сложным.\n\n"
            f"Куда: {target}",
            parent=self,
        )
        if not agreed:
            return
        self._scanning = True
        self._generation += 1
        generation = self._generation
        limit = self._limit()
        self.progress.set(0)
        self.status.configure(text=f"Сложность 0/{len(files)}")

        def work() -> None:
            ranked: list[tuple[Recommendation, Path]] = []
            for index, path in enumerate(files, start=1):
                if generation != self._generation:
                    return
                advice = recommend_file(path, limit)
                ranked.append((advice, path))
                self.after(0, lambda done=index, total=len(files), token=generation: self._scan_progress(done, total, token))
            self.after(0, lambda: self._spread_finished(ranked, target, generation))

        threading.Thread(target=work, daemon=True).start()

    def _spread_finished(self, ranked: list[tuple[Recommendation, Path]], target: Path, generation: int) -> None:
        if generation != self._generation:
            return
        ranked.sort(key=lambda item: (item[0].rank, item[0].largest, item[1].name.lower()))
        lines = [f"Сетка\tфайл\tстолбцы\tстроки\tпохожих\tвсего\tподходит"]
        moved = 0
        numbers: dict[str, int] = {}
        try:
            for advice, path in ranked:
                if not path.exists():
                    continue
                folder = target / advice.folder
                number = numbers.get(advice.folder, _next_number(folder))
                dest = folder / f"{number:03d}{path.suffix.lower()}"
                while dest.exists():
                    number += 1
                    dest = folder / f"{number:03d}{path.suffix.lower()}"
                move_image_to(path, dest)
                numbers[advice.folder] = number + 1
                lines.append(
                    f"{advice.folder}\t{dest.name}\t{advice.cols}\t{advice.rows}\t{advice.largest}\t{advice.total}\t"
                    f"{'да' if advice.fits else 'нет'}"
                )
                moved += 1
        except Exception as exc:
            self._scanning = False
            self.status.configure(text=str(exc), text_color="#f0a0a0")
            return
        report = target / "grids.txt"
        previous = report.read_text(encoding="utf-8") if report.exists() else ""
        block = "\n".join(lines) + "\n"
        report.write_text((previous + ("\n" if previous else "") + block).strip() + "\n", encoding="utf-8")
        self._scanning = False
        self.progress.set(1)
        self._queue = []
        self._show_empty(f"Разложено {moved}. Сетки — в {report.name}")

    def _load_preview(self, path: Path, fit: tuple[int, int], analysis: Analysis) -> Image.Image:
        with Image.open(path) as image:
            image = ImageOps.exif_transpose(image) or image
            image = image.convert("RGB")
            image.thumbnail(fit, Image.Resampling.LANCZOS)
            if self.grid_var.get() and not analysis.error:
                image = paint_grid(image, analysis)
            return image

    def _stage_size(self) -> tuple[int, int]:
        return max(1, self.stage.winfo_width() - 24), max(1, self.stage.winfo_height() - 24)

    def _show_empty(self, text: str) -> None:
        self._photo = None
        self.preview.configure(image=None, text=text)
        self.status.configure(text=text, text_color="#c5cad6")

    def _on_left(self, _event) -> str:
        self._act(self._move_current)
        return "break"

    def _on_right(self, _event) -> str:
        self._act(self._delete_current)
        return "break"

    def _act(self, action) -> None:
        now = time.monotonic()
        if now < self._lock_until or self._scanning or not self._queue:
            return
        self._lock_until = now + 0.4
        action()

    def _move_current(self) -> None:
        path = self._queue[self._index]
        target = self._target()
        if not self.target_entry.get().strip():
            self.status.configure(text="Выберите папку, куда переносить", text_color="#f0a0a0")
            return
        try:
            move_image(path, target)
        except Exception as exc:
            self.status.configure(text=str(exc), text_color="#f0a0a0")
            return
        self._drop_current()

    def _delete_current(self) -> None:
        path = self._queue[self._index]
        try:
            recycle_image(path)
        except Exception as exc:
            self.status.configure(text=str(exc), text_color="#f0a0a0")
            return
        self._drop_current()

    def _drop_current(self) -> None:
        if self._queue:
            self._queue.pop(self._index)
        if self._index >= len(self._queue):
            self._index = max(0, len(self._queue) - 1)
        self._show_current()

    def _load(self) -> None:
        source = Path(self._settings.get("review_source") or _preset_path("Кампания"))
        target = Path(self._settings.get("review_target") or (Path.home() / "Pictures" / "JigsawKeep"))
        self.source_menu.set(_preset_title(source))
        self.target_menu.set(_preset_title(target))
        self._set_entry(self.source_entry, source)
        self._set_entry(self.target_entry, target)
        self.cols_var.set(str(self._settings.get("review_cols", 8)))
        self.rows_var.set(str(self._settings.get("review_rows", 6)))
        self.limit_var.set(str(self._settings.get("review_limit", 4)))
        self.grid_var.set(bool(self._settings.get("review_grid", True)))
        self.only_bad_var.set(bool(self._settings.get("review_only_bad", False)))

    def _on_close(self) -> None:
        self._generation += 1
        data = dict(self._settings)
        data.update(
            {
                "review_source": self.source_entry.get().strip(),
                "review_target": self.target_entry.get().strip(),
                "review_cols": self._cols(),
                "review_rows": self._rows(),
                "review_limit": self._limit(),
                "review_grid": self.grid_var.get(),
                "review_only_bad": self.only_bad_var.get(),
            }
        )
        try:
            save_settings(data)
        except Exception:
            pass
        self.destroy()


def _next_number(folder: Path) -> int:
    highest = 0
    if folder.is_dir():
        for path in folder.iterdir():
            if path.is_file() and path.stem.isdigit():
                highest = max(highest, int(path.stem))
    return highest + 1


def _preset_path(label: str) -> Path | None:
    for _item_id, title, path in DESTINATIONS:
        if title == label:
            return path
    return None


def _preset_title(path: Path) -> str:
    for _item_id, title, preset in DESTINATIONS:
        if str(preset) == str(path):
            return title
    return "Своя папка"


def _parse(var: ctk.StringVar, default: int, lo: int, hi: int) -> int:
    try:
        value = int(str(var.get()).strip())
    except ValueError:
        return default
    return max(lo, min(hi, value))


def _cache_key(path: Path, cols: int, rows: int, limit: int) -> tuple:
    try:
        stamp = path.stat().st_mtime_ns
    except OSError:
        stamp = 0
    return (str(path), stamp, cols, rows, limit)


def run_gui() -> None:
    _enable_dpi()
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    ReviewerApp().mainloop()
