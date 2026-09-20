from __future__ import annotations

import os
import subprocess
import sys
import threading
import tkinter.filedialog as filedialog
from pathlib import Path

import customtkinter as ctk
from PIL import Image

from collector.categories import CATEGORIES, DEFAULT_SELECTED, custom_category
from collector.models import CollectOptions
from collector.paths import DESTINATIONS, destination_path
from collector.pipeline import collect_images
from collector.proxy import resolve_proxy
from collector.storage import load_settings, save_settings

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


class CollectorApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Сборщик картинок для пазлов")
        self.geometry("1180x780")
        self.minsize(1040, 700)
        self.configure(fg_color="#16181d")
        self._cancel = threading.Event()
        self._busy = False
        self._preview_ref = None
        self._settings = load_settings()
        self._build()
        self._load_from_settings()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(16, 8))
        ctk.CTkLabel(
            header,
            text="Картинки для Jigsaw Puzzles",
            font=ctk.CTkFont(size=24, weight="bold"),
        ).pack(anchor="w")
        ctk.CTkLabel(
            header,
            text="Открытые источники → WebP → 01.webp, 02.webp… в StreamingAssets. Авторы — в credits.txt (для игры — в Assets/Content).",
            text_color="#9aa3b2",
            font=ctk.CTkFont(size=13),
        ).pack(anchor="w", pady=(2, 0))

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=16, pady=4)
        body.grid_columnconfigure(0, weight=0)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        left = ctk.CTkScrollableFrame(body, width=520, fg_color="#1e2128", corner_radius=14)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        right = ctk.CTkFrame(body, fg_color="#1e2128", corner_radius=14)
        right.grid(row=0, column=1, sticky="nsew")

        self._section(left, "Куда сохранять")
        self.dest_var = ctk.StringVar(value="campaign")
        dest_row = ctk.CTkFrame(left, fg_color="transparent")
        dest_row.pack(fill="x", padx=12, pady=(0, 8))
        labels = [title for _id, title, _path in DESTINATIONS]
        self.dest_menu = ctk.CTkOptionMenu(
            dest_row,
            values=labels,
            command=self._on_dest_label,
            width=240,
        )
        self.dest_menu.pack(side="left")
        self.browse_btn = ctk.CTkButton(dest_row, text="Папка…", width=90, command=self._browse)
        self.browse_btn.pack(side="left", padx=8)
        self.path_entry = ctk.CTkEntry(left, height=36)
        self.path_entry.pack(fill="x", padx=12, pady=(0, 12))

        nums = ctk.CTkFrame(left, fg_color="transparent")
        nums.pack(fill="x", padx=12, pady=(0, 8))
        self.count_var = self._labeled_entry(nums, "Сколько фото", "50", 0)
        self.start_var = self._labeled_entry(nums, "Номер с", "1", 1)
        self.pad_var = self._labeled_entry(nums, "Цифр в имени", "2", 2)
        ctk.CTkLabel(
            left,
            text="Пример: старт 1 и 2 цифры → 01.webp, 02.webp. Старт 51 → 51.webp.",
            text_color="#8b93a7",
            font=ctk.CTkFont(size=12),
            wraplength=470,
            justify="left",
        ).pack(anchor="w", padx=12, pady=(0, 12))

        self._section(left, "Категории")
        grid = ctk.CTkFrame(left, fg_color="transparent")
        grid.pack(fill="x", padx=12, pady=(0, 8))
        self.cat_vars: dict[str, ctk.BooleanVar] = {}
        for index, category in enumerate(CATEGORIES):
            var = ctk.BooleanVar(value=category.id in DEFAULT_SELECTED)
            self.cat_vars[category.id] = var
            box = ctk.CTkCheckBox(grid, text=category.title, variable=var)
            box.grid(row=index // 2, column=index % 2, sticky="w", pady=4, padx=(0, 16))
        ctk.CTkLabel(left, text="Свой запрос (дополнительно)", text_color="#9aa3b2").pack(anchor="w", padx=12)
        self.query_entry = ctk.CTkEntry(left, placeholder_text="например: Japanese temple autumn")
        self.query_entry.pack(fill="x", padx=12, pady=(0, 12))

        self._section(left, "Обработка")
        flags = ctk.CTkFrame(left, fg_color="transparent")
        flags.pack(fill="x", padx=12, pady=(0, 6))
        self.landscape_var = ctk.BooleanVar(value=True)
        self.crop_var = ctk.BooleanVar(value=True)
        self.skip_var = ctk.BooleanVar(value=True)
        self.repeat_var = ctk.BooleanVar(value=True)
        self.credits_var = ctk.BooleanVar(value=True)
        self.proxy_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(flags, text="Только альбомные", variable=self.landscape_var).grid(row=0, column=0, sticky="w", pady=3)
        ctk.CTkCheckBox(flags, text="Кадр 16:9", variable=self.crop_var).grid(row=0, column=1, sticky="w", pady=3, padx=8)
        ctk.CTkCheckBox(flags, text="Не затирать файлы", variable=self.skip_var).grid(row=1, column=0, sticky="w", pady=3)
        ctk.CTkCheckBox(flags, text="Не повторять прошлые", variable=self.repeat_var).grid(row=1, column=1, sticky="w", pady=3, padx=8)
        ctk.CTkCheckBox(flags, text="Писать credits.txt", variable=self.credits_var).grid(row=2, column=0, sticky="w", pady=3)
        ctk.CTkCheckBox(flags, text="Локальный прокси", variable=self.proxy_var, command=self._refresh_proxy_label).grid(
            row=2, column=1, sticky="w", pady=3, padx=8
        )
        self.proxy_entry = ctk.CTkEntry(left, placeholder_text="Адрес прокси, пусто = определить автоматически")
        self.proxy_entry.pack(fill="x", padx=12, pady=(0, 4))
        self.proxy_label = ctk.CTkLabel(left, text="", text_color="#8b93a7", font=ctk.CTkFont(size=12), wraplength=470, justify="left")
        self.proxy_label.pack(anchor="w", padx=12, pady=(0, 8))

        proc = ctk.CTkFrame(left, fg_color="transparent")
        proc.pack(fill="x", padx=12, pady=(4, 4))
        self.max_var = self._labeled_entry(proc, "Макс. сторона", "1920", 0)
        self.quality_var = self._labeled_entry(proc, "Качество до", "75", 1)
        self.max_kb_var = self._labeled_entry(proc, "Макс. КБ файла", "220", 2)
        ctk.CTkLabel(
            left,
            text="Каждый WebP сжимается под вес: сначала качество, если не влезает — чуть меньше разрешение. 0 КБ = без лимита.",
            text_color="#8b93a7",
            font=ctk.CTkFont(size=12),
            wraplength=470,
            justify="left",
        ).pack(anchor="w", padx=12, pady=(0, 12))

        self._section(left, "Источники")
        self.src_vars = {
            "wikimedia": ctk.BooleanVar(value=True),
            "openverse": ctk.BooleanVar(value=True),
            "pexels": ctk.BooleanVar(value=False),
            "unsplash": ctk.BooleanVar(value=False),
            "pixabay": ctk.BooleanVar(value=False),
        }
        src_frame = ctk.CTkFrame(left, fg_color="transparent")
        src_frame.pack(fill="x", padx=12, pady=(0, 4))
        ctk.CTkCheckBox(src_frame, text="Wikimedia Commons (без ключа)", variable=self.src_vars["wikimedia"]).pack(anchor="w", pady=2)
        ctk.CTkCheckBox(src_frame, text="Openverse / CC (без ключа)", variable=self.src_vars["openverse"]).pack(anchor="w", pady=2)
        ctk.CTkCheckBox(src_frame, text="Pexels", variable=self.src_vars["pexels"]).pack(anchor="w", pady=(8, 2))
        self.pexels_key = ctk.CTkEntry(src_frame, placeholder_text="Ключ Pexels")
        self.pexels_key.pack(fill="x", pady=(0, 6))
        ctk.CTkCheckBox(src_frame, text="Unsplash", variable=self.src_vars["unsplash"]).pack(anchor="w", pady=2)
        self.unsplash_key = ctk.CTkEntry(src_frame, placeholder_text="Ключ Unsplash Access Key")
        self.unsplash_key.pack(fill="x", pady=(0, 6))
        ctk.CTkCheckBox(src_frame, text="Pixabay", variable=self.src_vars["pixabay"]).pack(anchor="w", pady=2)
        self.pixabay_key = ctk.CTkEntry(src_frame, placeholder_text="Ключ Pixabay")
        self.pixabay_key.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(
            left,
            text="Без ключей хватает Commons (избранные фото) и Openverse. Pexels/Unsplash дают более «стоковый» вид.",
            text_color="#8b93a7",
            wraplength=470,
            justify="left",
            font=ctk.CTkFont(size=12),
        ).pack(anchor="w", padx=12, pady=(0, 16))

        preview_box = ctk.CTkFrame(right, fg_color="#14161b", corner_radius=12)
        preview_box.pack(fill="x", padx=14, pady=14)
        self.preview = ctk.CTkLabel(preview_box, text="Превью появится после первого файла", height=210, text_color="#7b8494")
        self.preview.pack(fill="x", padx=8, pady=8)

        self.progress = ctk.CTkProgressBar(right, height=8)
        self.progress.pack(fill="x", padx=14, pady=(0, 8))
        self.progress.set(0)
        self.status = ctk.CTkLabel(right, text="Готово к сбору", text_color="#c5cad6", anchor="w")
        self.status.pack(fill="x", padx=16)

        self.log = ctk.CTkTextbox(right, font=ctk.CTkFont(family="Consolas", size=12))
        self.log.pack(fill="both", expand=True, padx=14, pady=12)
        self.log.configure(state="disabled")

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(fill="x", padx=20, pady=(4, 16))
        self.start_btn = ctk.CTkButton(
            buttons,
            text="Собрать",
            width=160,
            height=40,
            fg_color=ACCENT,
            text_color="#102043",
            font=ctk.CTkFont(size=15, weight="bold"),
            command=self._start,
        )
        self.start_btn.pack(side="left")
        self.stop_btn = ctk.CTkButton(
            buttons,
            text="Стоп",
            width=100,
            height=40,
            fg_color="#3a3f4b",
            command=self._stop,
            state="disabled",
        )
        self.stop_btn.pack(side="left", padx=8)
        ctk.CTkButton(buttons, text="Открыть папку", width=130, height=40, fg_color="#3a3f4b", command=self._open_folder).pack(
            side="left"
        )
        ctk.CTkButton(buttons, text="Пробные 3 фото", width=150, height=40, fg_color="#3a3f4b", command=self._trial).pack(
            side="left", padx=8
        )
        ctk.CTkButton(buttons, text="Перенумеровать", width=150, height=40, fg_color="#3a3f4b", command=self._open_renamer).pack(
            side="left"
        )

    def _section(self, parent, title: str) -> None:
        ctk.CTkLabel(parent, text=title, font=ctk.CTkFont(size=15, weight="bold"), text_color=ACCENT).pack(
            anchor="w", padx=12, pady=(10, 6)
        )

    def _labeled_entry(self, parent, label: str, default: str, column: int) -> ctk.StringVar:
        cell = ctk.CTkFrame(parent, fg_color="transparent")
        cell.grid(row=0, column=column, padx=(0, 10), sticky="w")
        ctk.CTkLabel(cell, text=label, text_color="#9aa3b2").pack(anchor="w")
        var = ctk.StringVar(value=default)
        ctk.CTkEntry(cell, textvariable=var, width=110, height=34).pack(anchor="w")
        return var

    def _on_dest_label(self, label: str) -> None:
        for dest_id, title, _path in DESTINATIONS:
            if title == label:
                self.dest_var.set(dest_id)
                if dest_id != "custom":
                    self._set_path(destination_path(dest_id))
                break

    def _set_path(self, path: Path) -> None:
        self.path_entry.delete(0, "end")
        self.path_entry.insert(0, str(path))

    def _browse(self) -> None:
        chosen = filedialog.askdirectory(initialdir=self.path_entry.get() or str(Path.home()))
        if chosen:
            self.dest_var.set("custom")
            self.dest_menu.set("Своя папка")
            self._set_path(Path(chosen))

    def _open_folder(self) -> None:
        path = Path(self.path_entry.get().strip() or ".")
        path.mkdir(parents=True, exist_ok=True)
        os.startfile(path)  # type: ignore[attr-defined]

    def _trial(self) -> None:
        self.count_var.set("3")
        self._start()

    def _open_renamer(self) -> None:
        self._persist()
        subprocess.Popen([sys.executable, "-m", "renamer"], cwd=str(Path(__file__).resolve().parents[1]))

    def _options_from_ui(self, count_override: int | None = None) -> CollectOptions:
        selected = [cat for cat in CATEGORIES if self.cat_vars[cat.id].get()]
        query = self.query_entry.get().strip()
        if query:
            selected.append(custom_category(query))
        if not selected:
            raise ValueError("Выберите хотя бы одну категорию или введите свой запрос.")
        enabled = [key for key, var in self.src_vars.items() if var.get()]
        if not enabled:
            raise ValueError("Включите хотя бы один источник.")
        return CollectOptions(
            categories=selected,
            custom_query=query,
            count=count_override or self._int(self.count_var, 1, 300, 50),
            start_number=self._int(self.start_var, 1, 99999, 1),
            pad_width=self._int(self.pad_var, 2, 4, 2),
            output_dir=Path(self.path_entry.get().strip()).expanduser(),
            landscape_only=self.landscape_var.get(),
            crop_16_9=self.crop_var.get(),
            max_side=self._int(self.max_var, 800, 4096, 1920),
            webp_quality=self._int(self.quality_var, 40, 95, 75),
            max_file_kb=self._int(self.max_kb_var, 0, 2000, 220),
            skip_existing=self.skip_var.get(),
            avoid_repeats=self.repeat_var.get(),
            write_credits=self.credits_var.get(),
            enabled_sources=enabled,
            pexels_key=self.pexels_key.get().strip(),
            unsplash_key=self.unsplash_key.get().strip(),
            pixabay_key=self.pixabay_key.get().strip(),
            use_local_proxy=self.proxy_var.get(),
            proxy_url=self.proxy_entry.get().strip(),
        )

    def _int(self, var: ctk.StringVar, lo: int, hi: int, default: int) -> int:
        try:
            value = int(str(var.get()).strip())
        except ValueError:
            return default
        return max(lo, min(hi, value))

    def _refresh_proxy_label(self) -> None:
        if not getattr(self, "proxy_label", None):
            return
        if not self.proxy_var.get():
            self.proxy_label.configure(text="Прокси выключен — прямое подключение.")
            return
        config = resolve_proxy(True, self.proxy_entry.get().strip())
        if config.enabled:
            self.proxy_label.configure(text=f"Трафик пойдёт через {config.display}")
        else:
            self.proxy_label.configure(text="Локальный прокси не найден. Укажите адрес вручную, например http://127.0.0.1:10809")

    def _start(self) -> None:
        if self._busy:
            return
        try:
            options = self._options_from_ui()
        except ValueError as exc:
            self._append_log(str(exc))
            self.status.configure(text=str(exc))
            return
        self._persist()
        self._cancel = threading.Event()
        self._busy = True
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.progress.set(0)
        self._append_log(f"Старт: {options.count} фото → {options.output_dir}")
        thread = threading.Thread(target=self._run, args=(options,), daemon=True)
        thread.start()

    def _stop(self) -> None:
        self._cancel.set()
        self.status.configure(text="Останавливаю…")

    def _run(self, options: CollectOptions) -> None:
        try:
            collect_images(options, progress=self._on_progress, cancel=self._cancel)
        except Exception as exc:
            self.after(0, lambda: self._append_log(f"Сбой: {exc}"))
        finally:
            self.after(0, self._done)

    def _on_progress(self, saved: int, total: int, message: str, path: Path | None) -> None:
        def apply() -> None:
            self.status.configure(text=message)
            self._append_log(message)
            if total:
                self.progress.set(saved / total)
            if path is not None:
                self._show_preview(path)

        self.after(0, apply)

    def _show_preview(self, path: Path) -> None:
        try:
            image = Image.open(path)
            image.thumbnail((420, 236))
            photo = ctk.CTkImage(light_image=image, dark_image=image, size=image.size)
            self._preview_ref = photo
            self.preview.configure(image=photo, text="")
        except Exception:
            pass

    def _done(self) -> None:
        self._busy = False
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")

    def _append_log(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _load_from_settings(self) -> None:
        data = self._settings
        dest_id = data.get("dest_id", "campaign")
        self.dest_var.set(dest_id)
        title = next((t for i, t, _p in DESTINATIONS if i == dest_id), DESTINATIONS[0][1])
        self.dest_menu.set(title)
        self._set_path(Path(data.get("output_dir") or destination_path(dest_id)))
        self.count_var.set(str(data.get("count", 50)))
        self.start_var.set(str(data.get("start_number", 1)))
        self.pad_var.set(str(data.get("pad_width", 2)))
        selected = set(data.get("categories") or DEFAULT_SELECTED)
        for cat_id, var in self.cat_vars.items():
            var.set(cat_id in selected)
        self.query_entry.insert(0, data.get("custom_query", ""))
        self.landscape_var.set(data.get("landscape_only", True))
        self.crop_var.set(data.get("crop_16_9", True))
        self.skip_var.set(data.get("skip_existing", True))
        self.repeat_var.set(data.get("avoid_repeats", True))
        self.credits_var.set(data.get("write_credits", True))
        self.proxy_var.set(data.get("use_local_proxy", data.get("use_cursor_proxy", True)))
        self.proxy_entry.delete(0, "end")
        self.proxy_entry.insert(0, data.get("proxy_url", ""))
        self._refresh_proxy_label()
        self.max_var.set(str(data.get("max_side", 1920)))
        self.quality_var.set(str(data.get("webp_quality", 75)))
        self.max_kb_var.set(str(data.get("max_file_kb", 220)))
        for key, var in self.src_vars.items():
            default = key in ("wikimedia", "openverse")
            var.set(data.get("sources", {}).get(key, default))
        self.pexels_key.insert(0, data.get("pexels_key", ""))
        self.unsplash_key.insert(0, data.get("unsplash_key", ""))
        self.pixabay_key.insert(0, data.get("pixabay_key", ""))

    def _persist(self) -> None:
        save_settings(
            {
                "dest_id": self.dest_var.get(),
                "output_dir": self.path_entry.get().strip(),
                "count": self._int(self.count_var, 1, 300, 50),
                "start_number": self._int(self.start_var, 1, 99999, 1),
                "pad_width": self._int(self.pad_var, 2, 4, 2),
                "categories": [cat_id for cat_id, var in self.cat_vars.items() if var.get()],
                "custom_query": self.query_entry.get().strip(),
                "landscape_only": self.landscape_var.get(),
                "crop_16_9": self.crop_var.get(),
                "skip_existing": self.skip_var.get(),
                "avoid_repeats": self.repeat_var.get(),
                "write_credits": self.credits_var.get(),
                "use_local_proxy": self.proxy_var.get(),
                "proxy_url": self.proxy_entry.get().strip(),
                "max_side": self._int(self.max_var, 800, 4096, 1920),
                "webp_quality": self._int(self.quality_var, 40, 95, 75),
                "max_file_kb": self._int(self.max_kb_var, 0, 2000, 220),
                "sources": {key: var.get() for key, var in self.src_vars.items()},
                "pexels_key": self.pexels_key.get().strip(),
                "unsplash_key": self.unsplash_key.get().strip(),
                "pixabay_key": self.pixabay_key.get().strip(),
            }
        )

    def _on_close(self) -> None:
        self._cancel.set()
        try:
            self._persist()
        except Exception:
            pass
        self.destroy()


def run_gui() -> None:
    _enable_dpi()
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    app = CollectorApp()
    app.mainloop()
