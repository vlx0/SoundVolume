# 🔊 SoundVolume

Планировщик системной громкости Windows 10/11. По расписанию
устанавливает нужный уровень через `keybd_event` — реальное
системное изменение, не виртуальный слой.

![Python](https://img.shields.io/badge/Python-3.8%2B-blue?logo=python)
![Platform](https://img.shields.io/badge/Platform-Windows%2010%2F11-0078d4?logo=windows)
![License](https://img.shields.io/badge/License-MIT-green)
![Dependencies](https://img.shields.io/badge/Dependencies-zero-brightgreen)

---

## ✨ Что делает

- 🔉 Mute / ±2% одной кнопкой, точная установка уровня через ползунок
- ⏰ Несколько **сценариев** с временем начала/конца и уровнем громкости
- 🌅 Окна через полночь работают автоматически (22:00 → 08:00)
- 📌 Режим **«Фиксировать»** — конкретный уровень % всегда, выше сценариев
- 💾 Настройки в `config.json`
- 🪶 **Без зависимостей** — только стандартная библиотека Python
- 📜 Ротация логов: 3 файла × 500 КБ

---

## 🚀 Запуск

```powershell
git clone https://github.com/<your-username>/SoundVolume.git
cd SoundVolume
python main.py
```

> Только Windows 10/11. `requirements.txt` пустой — никакого `pip install`.
> Для запуска без консоли: `pythonw.exe main.py`.

При первом запуске откроется окно с двумя сценариями по умолчанию:
`08:00 → 22:00 → 70%` и `22:00 → 08:00 → 0%`. Внизу справа —
переключатель **«Фиксировать»**: `(авто) / 0% / 25% / 50% / 75% / 100%`.

---

## 🎛 Режимы работы

**Авто по сценариям** (по умолчанию) — планировщик раз в 30 сек
проверяет сценарии и применяет уровень первого попавшего в окно.

**Фиксировано N%** — игнорирует все сценарии, всегда держит выбранный
уровень. Удобно для звонков, видео, фокусировки. В statusbar
отображается `FORCED → 50%`.

---

## 🖱 Как это работает

Когда планировщик тикает:

1. Если `force_level` задан — сразу применяет его (выше сценариев).
2. Иначе — берёт первый активный сценарий (порядок = порядок в списке).
3. `volume.py` запускает `volume.ps1`.
4. PowerShell через `Add-Type + C#` дёргает `keybd_event` с виртуальными
   клавишами `VK_VOLUME_UP` (0xAF) / `VK_VOLUME_DOWN` (0xAE) / `VK_VOLUME_MUTE` (0xAD).
5. Windows обрабатывает их как обычное нажатие кнопок громкости
   на клавиатуре — реальная системная громкость меняется.

Громкость — **настоящая**, не виртуальный слой.

> ⚠️ Шаг у `VK_VOLUME_UP/DOWN` = 2% (зависит от аудио-драйвера).
> Текущий уровень нельзя прочитать без COM — `known_muted` хранится
> в `config.json`.

---

## 📁 Структура

```
SoundVolume/
├── main.py              # Точка входа
├── app.py               # Tkinter GUI (ползунок, Treeview, force combobox)
├── volume.py            # Обёртка subprocess → PowerShell
├── volume.ps1           # keybd_event VK_VOLUME_UP/DOWN/MUTE
├── scheduler.py         # Фоновый поток-планировщик (snapshot под RLock)
├── config.py            # JSON-конфиг + Scenario dataclass + RLock
├── logger.py            # RotatingFileHandler + StreamHandler
├── config.json          # Создаётся при первом «Сохранить»
├── requirements.txt     # Пустой (только stdlib)
├── LICENSE              # MIT
└── README.md
```

## 🎛 Настройки `config.json`

```json
{
  "scenarios": [
    {
      "start_hour": 8, "start_minute": 0,
      "end_hour": 22, "end_minute": 0,
      "level": 70,
      "enabled": true
    },
    {
      "start_hour": 22, "start_minute": 0,
      "end_hour": 8, "end_minute": 0,
      "level": 0,
      "enabled": true
    }
  ],
  "auto_start": true,
  "force_level": null,
  "known_muted": false
}
```

| Поле | Тип | Что значит |
|---|---|---|
| `scenarios[].start_hour` / `start_minute` | 0..23 / 0..59 | Когда переключить |
| `scenarios[].end_hour` / `end_minute` | 0..23 / 0..59 | Когда переключить обратно |
| `scenarios[].level` | 0..100 | Целевой уровень громкости (%) |
| `scenarios[].enabled` | bool | Сценарий активен |
| `auto_start` | bool | Запускать планировщик сразу при старте |
| `force_level` | 0..100 / `null` | Фиксированный уровень (выше сценариев) |
| `known_muted` | bool | Последнее известное состояние mute |

---

## 🪟 Сборка в .exe

```powershell
pip install pyinstaller
pyinstaller --onefile --noconsole --name SoundVolume main.py
```

---

## 🐛 Известные ограничения

- Только Windows 10/11 (использует `user32!keybd_event`).
- Шаг громкости = 2% (зависит от драйвера, не документировано Microsoft).
- Текущий уровень громкости **нельзя прочитать** без COM — поэтому
  храним `known_muted` вручную. Если что-то ещё меняет громкость
  (медиа-плеер, другая утилита), наш трекинг может разойтись.
- При включённом `force_level` ручное изменение громкости
  будет перезаписано при следующем тике планировщика (30 сек).

## 📝 Лицензия

MIT — делай что хочешь, только копирайт сохрани.