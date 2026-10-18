"""volume.py — Python-обёртка для volume.ps1.

Публичный API:
    mute()       — toggle mute (нужно вызывать дважды для гарантированного toggle)
    vol_up(n)    — нажать Up n раз
    vol_down(n)  — нажать Down n раз
    set_level(target, current) — двигаемся от current к target (нечёткое число шагов)
"""

import subprocess
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_PS = _HERE / "volume.ps1"

# Шаг в процентах на одну клавишу Up/Down в Windows 10/11.
# Зависит от драйвера, но обычно 2%.
STEP_PER_KEY = 2


def _run(action: str, n: int = 0, timeout: int = 10):
    if not _PS.exists():
        return False
    cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
           "-File", str(_PS), action, str(n)]
    try:
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if r.returncode != 0:
            print(f"[volume] ps exit={r.returncode}: {r.stderr.strip()}", file=sys.stderr)
            return False
        return True
    except subprocess.TimeoutExpired:
        print("[volume] ps timeout", file=sys.stderr)
        return False
    except FileNotFoundError:
        print("[volume] powershell not found", file=sys.stderr)
        return False
    except Exception as e:
        print(f"[volume] error: {e}", file=sys.stderr)
        return False


def mute() -> bool:
    return _run("mute", n=0)


def vol_up(n: int = 1) -> bool:
    return _run("up", n=max(0, int(n)))


def vol_down(n: int = 1) -> bool:
    return _run("down", n=max(0, int(n)))


def set_level(target: int, current: int) -> bool:
    """
    Двигаем громкость от current к target шагами по STEP_PER_KEY.
    Если разница больше 50% — сначала mute → ждём → серия Up/Down → unmute.
    """
    target = max(0, min(100, int(target)))
    current = max(0, min(100, int(current)))
    diff = target - current
    if diff == 0:
        return True
    if abs(diff) > 50:
        # Переполнение через mute поможет
        mute()
        # Небольшая задержка, иначе PS не успеет
        import time
        time.sleep(0.05)
    n_steps = abs(diff) // STEP_PER_KEY
    if n_steps == 0:
        n_steps = 1
    return vol_up(n_steps) if diff > 0 else vol_down(n_steps)


if __name__ == "__main__":
    import sys as _s
    if len(_s.argv) < 2:
        print("usage: python volume.py mute|up N|down N")
    elif _s.argv[1] == "mute":
        print("ok" if mute() else "fail")
    elif _s.argv[1] in ("up", "down") and len(_s.argv) >= 3:
        n = int(_s.argv[2])
        fn = vol_up if _s.argv[1] == "up" else vol_down
        print("ok" if fn(n) else "fail")