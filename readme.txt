RunePilot (LoLAutomation)
========================

RunePilot; League of Legends istemcisi (LCU API) ile haberleşen, seçim ekranında ban/şampiyon seçimi ve rün sayfası ayarlama işlemlerini otomatikleştiren bir masaüstü uygulamasıdır.

Amaç
----
Uzun seçim/ban ekranlarında bilgisayar başında beklemeden; önceden kaydettiğiniz tercihlere göre otomatik ban + şampiyon seçimi yapmak ve seçilen şampiyon için uygun rün sayfasını hazırlamaktır.

Gereksinimler
-------------
- Windows
- Çalışır durumda League of Legends Client (oyuna giriş yapılmış olmalı)
- Kaynak koddan çalıştırmak için: Python 3.13+

Kurulum (kaynak kod)
--------------------
1) Bağımlılıkları kurun:
   pip install -r requirements.txt
2) LoL Client'ı açın.
3) Uygulamayı başlatın:
   python run_app.py

Sadece API (geliştirme)
-----------------------
python main.py

EXE oluşturma (PyInstaller)
---------------------------
python -m PyInstaller --clean -y run_app.spec

Çıktı: dist/RunePilot.exe

EXE ile çalışma
---------------
- dist klasöründeki .exe dosyası ile proje kökündeki runes.json aynı dizinde olmalı.
- LoL Client açıkken .exe'yi çalıştırın.

Arayüz / İlk kullanım
---------------------
- Uygulamaya ilk girişte (1 kere) her rol için ban ve seçim tercihlerinizi kaydedin. Sonraki açılışlarda son kayıt otomatik yüklenir.
- Şampiyon seçmeden önce "Yenile" butonuna basın; bu, hesabınızdaki şampiyonları uygulamaya çeker/günceller.
- Şampiyonu seçince sağ tarafta rün bölümü açılır:
  - "Rünler" ile özel (custom) rün sayfanızı oluşturabilirsiniz.
  - Özel rün oluşturmazsanız, runes.json içindeki ilgili şampiyon için en yüksek kazanma oranına sahip rün sayfası otomatik oluşturulur/kaydedilir.

Notlar
------
- Kullanıcı ayarları: %APPDATA%\\RunePilot\\user_config.json
- Lockfile yolu farklıysa LOL_LOCKFILE ortam değişkeni ile override edebilirsiniz.
