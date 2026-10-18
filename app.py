"""
app.py
======
Tkinter GUI для SoundVolume.

Окно:
    * Текущий уровень (%) + mute-индикатор
    * Ползунок 0..100
    * Кнопки ±2%, mute, apply
    * Список сценариев
    * Force combobox (авто / N%)
"""

import threading
import tkinter as tk
from tkinter import messagebox, ttk

from config import Config, Scenario, config_path
from logger import setup as log_setup
from scheduler import Scheduler
from volume import vol_up, vol_down, mute as vol_mute, set_level


log = log_setup()


class VolumeController:
    """Адаптер scheduler → volume.py."""

    def __init__(self, known_muted: bool = False, on_change=None):
        self._current_level = 50
        self._muted = known_muted
        self._on_change = on_change

    def apply(self, level: int) -> bool:
        level = max(0, min(100, int(level)))
        ok = set_level(level, self._current_level)
        if ok:
            self._current_level = level
            self._muted = (level == 0)
            if self._on_change:
                self._on_change(level, self._muted)
        return ok

    def disable(self) -> bool:
        return True  # без сценария — оставляем как есть

    @property
    def current_level(self) -> int:
        return self._current_level

    @property
    def muted(self) -> bool:
        return self._muted


class VolumeApp:
    REFRESH_INTERVAL_MS = 30_000

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("SoundVolume")
        self.root.geometry("520x440")
        self.root.minsize(480, 380)

        try:
            self.root.iconbitmap(default="")
        except Exception:
            pass

        self.config = Config.load(config_path())
        self.controller = VolumeController(
            known_muted=self.config.known_muted,
            on_change=self._on_level_changed,
        )
        self.scheduler = Scheduler(
            config=self.config,
            filter_=self.controller,
            on_state_change=self._on_sched_state,
        )

        self._build_ui()
        self._refresh_status()

        if self.config.auto_start:
            self.scheduler.start()

        self.root.after(self.REFRESH_INTERVAL_MS, self._tick_refresh)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        # top: текущий уровень + ползунок
        top = ttk.Frame(self.root, padding=8)
        top.pack(fill=tk.X)

        ttk.Label(top, text="Уровень:", font=("", 10)).pack(side=tk.LEFT)
        self.level_var = tk.StringVar(value="—")
        ttk.Label(top, textvariable=self.level_var, font=("", 12, "bold")).pack(
            side=tk.LEFT, padx=(6, 0)
        )
        self.mute_var = tk.StringVar(value="")
        ttk.Label(top, textvariable=self.mute_var, font=("", 10, "italic")).pack(
            side=tk.LEFT, padx=(8, 0)
        )

        # slider frame
        sl = ttk.Frame(self.root, padding=(8, 0, 8, 4))
        sl.pack(fill=tk.X)
        ttk.Label(sl, text="Громкость:").pack(side=tk.LEFT)
        self.scale_var = tk.IntVar(value=self.config.known_muted and 0 or 50)
        self.scale = ttk.Scale(
            sl, from_=0, to=100, orient=tk.HORIZONTAL, variable=self.scale_var,
            command=lambda v: self._on_scale_change(int(float(v))),
        )
        self.scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 8))
        self.scale_lbl = ttk.Label(sl, text="50%", width=4)
        self.scale_lbl.pack(side=tk.LEFT)

        # buttons
        btns = ttk.Frame(self.root, padding=8)
        btns.pack(fill=tk.X)
        ttk.Button(btns, text="-2%", command=lambda: self._step(-2)).pack(side=tk.LEFT)
        ttk.Button(btns, text="+2%", command=lambda: self._step(+2)).pack(
            side=tk.LEFT, padx=(4, 0)
        )
        ttk.Button(btns, text="Mute", command=self._mute).pack(side=tk.LEFT, padx=(12, 0))
        ttk.Button(btns, text="Apply", command=self._apply_from_scale).pack(
            side=tk.RIGHT
        )

        # middle: список сценариев
        mid = ttk.LabelFrame(self.root, text="Сценарии (время → уровень %)", padding=8)
        mid.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 4))

        cols = ("start", "end", "level", "enabled")
        self.tree = ttk.Treeview(mid, columns=cols, show="headings", height=6)
        self.tree.heading("start", text="Начало")
        self.tree.heading("end", text="Конец")
        self.tree.heading("level", text="Уровень")
        self.tree.heading("enabled", text="Вкл")
        self.tree.column("start", width=110, anchor="center")
        self.tree.column("end", width=110, anchor="center")
        self.tree.column("level", width=80, anchor="center")
        self.tree.column("enabled", width=60, anchor="center")
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        sb = ttk.Scrollbar(mid, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.LEFT, fill=tk.Y)

        self.tree.bind("<Double-1>", self._on_edit_cell)

        # middle right buttons
        sbtns = ttk.Frame(self.root, padding=(8, 0))
        sbtns.pack(fill=tk.X)
        ttk.Button(sbtns, text="+ Добавить", command=self._on_add).pack(side=tk.LEFT)
        ttk.Button(sbtns, text="− Удалить", command=self._on_remove).pack(
            side=tk.LEFT, padx=(4, 0)
        )

        # bottom: force + auto + save + exit
        bot = ttk.Frame(self.root, padding=8)
        bot.pack(fill=tk.X)

        self.auto_var = tk.BooleanVar(value=self.config.auto_start)
        ttk.Checkbutton(
            bot,
            text="Автопланировщик",
            variable=self.auto_var,
            command=self._on_toggle_auto,
        ).pack(side=tk.LEFT)

        ttk.Label(bot, text="  Фиксировать:").pack(side=tk.LEFT)
        force_display = "(авто)" if self.config.force_level is None else f"{self.config.force_level}%"
        self.force_var = tk.StringVar(value=force_display)
        ttk.Combobox(
            bot,
            textvariable=self.force_var,
            values=("(авто)", "0%", "25%", "50%", "75%", "100%"),
            state="readonly",
            width=8,
        ).pack(side=tk.LEFT, padx=(4, 0))
        self.force_var.trace_add("write", lambda *_: self._on_force_change())

        ttk.Button(bot, text="Сохранить", command=self._save).pack(side=tk.RIGHT)
        ttk.Button(bot, text="Выход", command=self.quit_app).pack(side=tk.RIGHT, padx=(0, 4))

        self.status_var = tk.StringVar(value="OK")
        ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W).pack(
            fill=tk.X, side=tk.BOTTOM
        )

        self._reload_tree()

    # ------------------------------------------------------------------ logic
    def _reload_tree(self):
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        for idx, s in enumerate(self.config.scenarios):
            self.tree.insert(
                "", "end", iid=str(idx),
                values=(s.start_str(), s.end_str(), f"{s.level}%",
                        "✓" if s.enabled else "—"),
            )

    def _refresh_status(self):
        lvl = self.controller.current_level
        muted = self.controller.muted
        self.level_var.set(f"{lvl}%")
        self.mute_var.set("(mute)" if muted else "")
        self.scale_var.set(lvl)
        self.scale_lbl.config(text=f"{lvl}%")

    def _on_level_changed(self, level: int, muted: bool):
        self.root.after(0, lambda: self._apply_level_ui(level, muted))

    def _apply_level_ui(self, level: int, muted: bool):
        self.level_var.set(f"{level}%")
        self.mute_var.set("(mute)" if muted else "")
        self.scale_var.set(level)
        self.scale_lbl.config(text=f"{level}%")
        self.config.known_muted = muted
        self.status_var.set(f"Установлено: {level}%")

    def _on_sched_state(self, in_window, level, label):
        if not in_window:
            self.root.after(0, lambda: self.status_var.set("Нет активного сценария"))
            return
        if label == "FORCED":
            self.root.after(0, lambda: self.status_var.set(f"FORCED → {level}%"))
        else:
            self.root.after(0, lambda: self.status_var.set(f"Активен: {label} → {level}%"))

    def _on_force_change(self, *_):
        sel = self.force_var.get()
        if sel == "(авто)":
            self.config.force_level = None
        else:
            try:
                self.config.force_level = int(sel.rstrip("%"))
            except ValueError:
                return
        self.scheduler.update_config(self.config)
        self._save()
        if self.config.force_level is not None:
            self.status_var.set(f"Фиксировано: {self.config.force_level}%")
        else:
            self.status_var.set("Авто по сценариям")

    def _on_toggle_auto(self):
        self.config.auto_start = self.auto_var.get()
        if self.config.auto_start:
            self.scheduler.start()
        else:
            self.scheduler.stop()
        self._save()

    def _step(self, delta: int):
        new_level = max(0, min(100, self.controller.current_level + delta))
        self._apply_target(new_level)

    def _apply_from_scale(self):
        self._apply_target(self.scale_var.get())

    def _apply_target(self, target: int):
        # В фоне, чтобы GUI не завис
        def worker():
            ok = self.controller.apply(target)
            self.root.after(0, lambda: self._after_apply(ok, target))
        threading.Thread(target=worker, daemon=True).start()

    def _after_apply(self, ok: bool, target: int):
        if ok:
            self.status_var.set(f"Применено: {target}%")
        else:
            messagebox.showerror("Ошибка", f"Не удалось применить {target}%")

    def _mute(self):
        def worker():
            ok = vol_mute()
            self.root.after(0, lambda: self._after_mute(ok))
        threading.Thread(target=worker, daemon=True).start()

    def _after_mute(self, ok: bool):
        if ok:
            self.config.known_muted = not self.config.known_muted
            muted = self.config.known_muted
            self.mute_var.set("(mute)" if muted else "")
            self.status_var.set("Mute toggled")
            self._save()
        else:
            messagebox.showerror("Ошибка", "Не удалось переключить mute")

    def _on_scale_change(self, value: int):
        # Ползунок двигается — обновляем label, но не применяем
        self.scale_lbl.config(text=f"{value}%")

    def _on_add(self):
        s = self.config.add_scenario()
        self._reload_tree()
        self._save()
        iid = str(len(self.config.scenarios) - 1)
        self.tree.selection_set(iid)
        self.tree.focus(iid)
        self._edit_scenario(iid)

    def _on_remove(self):
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        self.config.remove_scenario(idx)
        self._reload_tree()
        self._save()

    def _on_edit_cell(self, _event):
        sel = self.tree.selection()
        if sel:
            self._edit_scenario(sel[0])

    def _edit_scenario(self, iid: str):
        idx = int(iid)
        s = self.config.scenarios[idx]

        win = tk.Toplevel(self.root)
        win.title(f"Сценарий #{idx + 1}")
        win.geometry("300x300")
        win.transient(self.root)
        win.grab_set()

        ttk.Label(win, text="Начало:").grid(row=0, column=0, sticky="w", padx=8, pady=4)
        sh = tk.IntVar(value=s.start_hour)
        sm = tk.IntVar(value=s.start_minute)
        ttk.Spinbox(win, from_=0, to=23, textvariable=sh, width=3).grid(row=0, column=1)
        ttk.Label(win, text=":").grid(row=0, column=2)
        ttk.Spinbox(win, from_=0, to=59, textvariable=sm, width=3).grid(row=0, column=3)

        ttk.Label(win, text="Конец:").grid(row=1, column=0, sticky="w", padx=8, pady=4)
        eh = tk.IntVar(value=s.end_hour)
        em = tk.IntVar(value=s.end_minute)
        ttk.Spinbox(win, from_=0, to=23, textvariable=eh, width=3).grid(row=1, column=1)
        ttk.Label(win, text=":").grid(row=1, column=2)
        ttk.Spinbox(win, from_=0, to=59, textvariable=em, width=3).grid(row=1, column=3)

        ttk.Label(win, text="Уровень %:").grid(row=2, column=0, sticky="w", padx=8, pady=4)
        lv = tk.IntVar(value=s.level)
        ttk.Spinbox(win, from_=0, to=100, textvariable=lv, width=5).grid(row=2, column=1)

        en_var = tk.BooleanVar(value=s.enabled)
        ttk.Checkbutton(win, text="Активен", variable=en_var).grid(
            row=3, column=0, columnspan=4, sticky="w", padx=8
        )

        def save_and_close():
            s.start_hour = sh.get()
            s.start_minute = sm.get()
            s.end_hour = eh.get()
            s.end_minute = em.get()
            s.level = lv.get()
            s.enabled = en_var.get()
            s.__post_init__()
            self._reload_tree()
            self._save()
            win.destroy()

        ttk.Button(win, text="OK", command=save_and_close).grid(
            row=4, column=0, columnspan=4, pady=8
        )

    def _save(self):
        try:
            self.config.save(config_path())
        except OSError as e:
            log.error("save failed: %s", e)
            self.status_var.set(f"ОШИБКА сохранения: {e}")
            return
        self.scheduler.update_config(self.config)
        self.status_var.set(f"Сохранено: {len(self.config.scenarios)} сценариев")

    def _tick_refresh(self):
        self._refresh_status()
        self.root.after(self.REFRESH_INTERVAL_MS, self._tick_refresh)

    def _on_close(self):
        self.quit_app()

    def quit_app(self):
        try:
            self.scheduler.stop()
        except Exception:
            pass
        try:
            self.config.save(config_path())
        except Exception:
            pass
        self.root.destroy()

    def run(self):
        self.root.mainloop()