# RunePilot

League of Legends istemcisi (LCU API) ile entegre çalışan; **FastAPI** (arka plan servisi) + **PyQt6** (masaüstü arayüz) tabanlı otomasyon aracıdır.

Detaylı bilgi ve kullanım adımları için [`readme.txt`](readme.txt) dosyasına bakın.

## Gereksinimler

- Windows
- Çalışan League of Legends Client
- Python 3.13+

## Çalıştırma

GUI + API beraber:

```powershell
python run_app.py
```

Sadece API (geliştirme amaçlı):

```powershell
python main.py
```

## EXE Derleme (PyInstaller)

```powershell
python -m PyInstaller --clean -y run_app.spec
```

Çıktı: `dist/RunePilot.exe`

## Notlar

- `runes.json` uygulama ile birlikte gelir ve önerilen rün verisini içerir.
- Kullanıcı ayarları (lokalde): `%APPDATA%\\RunePilot\\user_config.json`
- LoL lockfile yolu farklıysa `LOL_LOCKFILE` ortam değişkeni ile override edebilirsiniz.
