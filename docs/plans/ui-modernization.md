# RunePilot — Modern arayüz geçiş planı

**Güncelleme:** 10 Kasım 2026 · **Durum:** Seçim/rün/kostüm ekranları hazır; masaüstü geçişi sürüyor.

**Kapsam değişikliği:** Kullanıcı kararıyla hesap yönetimi, parola saklama ve
otomatik Riot girişi tamamen kaldırıldı. Aşağıdaki eski iş yükü tablolarındaki
P6 ve hesap uyumluluğu varsayımları tarihsel bilgi olarak kalır; aktif plana
geri eklenmeyecek. Riot/League girişi kullanıcı tarafından yapılır.

**Karar:** PyQt ekranlarını yeniden biçimlendirmek yerine React + TypeScript
arayüzüne geçilecek. Masaüstü kabuğu Tauri 2, iş katmanı mevcut Python/FastAPI
olacak. Öncelik, gerçek uygulamaya bağlı modern ekranları küçük teslimlerle
kullanabilmek. Kurulum ve otomatik güncelleme ilk ekran teslimini bekletmeyecek.

## Aktif kapsam ve teslim sırası

**Uygulama durumu:** [React geliştirme ekranı](../../frontend/README.md) tema,
roller, arama/sayfalama, seçim/ban ve öncelik sırasıyla hazır. İkinci adımda
oyun/rol tercihleri, büyüler, sıralı kalıcı kayıt, ETag çakışma koruması,
başlat/durdur, çalışan otomasyona güvenli ayar güncelleme ve kontrollü oturum
bitirme bağlandı. Portreler ve üç dolu satıra uyarlanan sayfalama da eklendi.
Derleme + 322 Python testi + 34 frontend testi + 31 tarayıcı
kontrolü geçti. Gerçek ayarlar/ETag okundu; yazma ve otomasyon testleri gerçek
profili değiştirmeyen test ortamlarında yapıldı. Canlı normal katalog (173
şampiyon) ve PNG portreleri doğrulandı; gerçek oyun içi uygulama kontrolü bekliyor.
Tauri uygulanmadı; Rust araçları PATH üzerinde bulunmadı ve yerel kabuk denemesi
henüz tamamlanmadı. Tarayıcıdaki doğrudan kapatmanın sınırları README'de açıklanır.

**Güncel seçim kuralı:** Bir şampiyon aynı rol içinde yalnızca bir tercihte yer
alabilir. Farklı roller bağımsızdır. Eski kayıtlardaki sonraki tekrarlar boş
slotlara dönüştürülür; ilk tercih, sıra ve şampiyon özelleştirmeleri korunur.
Bu karar, aşağıdaki tarihsel geniş plandaki tekrarları koruma varsayımını günceller.

| Sıra | Teslim | Bitti sayılması için |
| --- | --- | --- |
| 1 | React/Vite iskeleti, ortak tema ve ilk şampiyon/ban ekranı | Gerçek API'den katalog/ayar okunur; yüklenme, bağlantı hatası ve tekrar deneme görünür |
| 2 | Şampiyon/ban akışının tamamlanması | Rol, üç sıralı seçim, büyüler, ayar kaydı ve otomasyon başlat/durdur çalışır |
| 3 | Rün editörü ve kostüm galerisi | Mevcut preset/seçimler kayıpsız taşınır; görseller eksikse kullanılabilir yedek durum gösterilir |
| 4 | Temel Tauri masaüstü çalıştırması | Pencere ve sahip olunan backend süreci düzgün kapanır; yapılandırma doğrudan açılır |

İlk teslimler geliştirme ortamında çalışır; tarayıcı önizlemesi kurulabilir
masaüstü sürümü olarak sunulmaz. Tauri araç zinciri ve küçük servis başlatma
denemesi erkenden kontrol edilir; React ekran geliştirmesinin tüm dağıtım
altyapısı tamamlanana kadar beklemesi gerekmez.

### İlk ekranda korunacak davranışlar

- Ayarlar yüklenmeden düzenleme/kayıt yapılmaz; yükleme hatası varsayılanlarla
  mevcut profili ezmez. Kayıtlar sıralanır ve son kayıt başarısızsa çıkış durur.
- Seçimler isimle değil kimlikle tutulur; katalog yenilemesi kullanıcı
  düzenlemesini, eksik kayıtlı şampiyonları veya seçim sırasını silmez.
- Arayüz backend'e API üzerinden erişir; otomasyon ve Riot/LCU mantığı Python'da
  kalır. Gerçek profile aynı anda Qt ve React yazmaz.
- Hesap yönetimi, parola saklama ve otomatik giriş kaldırıldı.
  Uygulama kapanırken otomasyonun/sahip olunan servisin açık kalması engellenir.

### Ayrı tutulacak sonraki işler

İmzalı otomatik güncelleme, kurulum/dağıtım hattının yenilenmesi, sistem tepsisi
ve bildirimlerde tam özellik eşitliği, temiz makine yayın doğrulaması ayrı
dağıtım aşamasıdır. Bunlar son kullanıcıya yayın öncesi yeniden ele alınacak;
ilk kullanılabilir ekranların önkoşulu değildir. Telefon kontrolü ertelenmiştir.

## İş yükü tahmininin düzeltilmesi

Önceki **320 kişi-saat**, tüm masaüstü özellikleri, paketleme, kurulum,
güncelleme ve yayın doğrulamasını bir arada ele alan geniş kapsamın tahminiydi.
Aktif ekran geliştirme planının teslim süresi olarak kullanılmayacak.
Sonraki konuşmadaki **2–4 iş günü** ise Qt üzerinde görsel yenilemeye aitti;
React/Tauri teknoloji geçişine uygulanamaz.

Teknoloji geçişi korunurken teslim kapsamı ayrıştırıldı. Yeni tahmin ilk gerçek
API'ye bağlı ekran
tamamlanınca; API uyumu, görsel ihtiyaçları ve yerel kabuk denemesinin sonuçları
üzerinden kalan işler için yapılacak. İlk ekran, dört ekranın tamamlanması,
masaüstü çalışma ve dağıtım ayrı ayrı raporlanacak.

Önceki detaylı iş dökümü aşağıda tarihsel referans olarak korunuyor. Aşağıdaki
P0–P9 sırası ve M1–M4 bütçeleri aktif teslim sırası veya güncel taahhüt değildir.
[Önceki tahmin hesabı](ui-modernization-estimate.json)

---

## Önceki geniş kapsamlı plan — 27 Ekim 2026

**Tarih:** 27 Ekim 2026 · **Durum:** Planlandı; uygulama başlamadı.

Hedef, şampiyon seçimi, banlama, rün ve kostüm ekranlarını modernleştirmek;
ardından hesap/giriş, sistem tepsisi, kurulum ve güncellemeyi aynı masaüstü
deneyimine taşımaktır. Önerilen yapı **React + TypeScript + Vite**, masaüstü
kabuğu **Tauri 2**, mevcut **Python + FastAPI** iş katmanlarıdır.

Tam kapsam için planlama bütçesi **320 kişi-saat**: 256 saat beklenen iş ve
64 saat belirsizlik payı. Tek deneyimli geliştiricinin haftada 30–35 net proje
saati ayırmasıyla yaklaşık **9–11 hafta** gerekir. Bu bir mühendislik tahminidir;
teslim tarihi taahhüdü değildir. P0 sonunda tahmin yeniden değerlendirilecek.

## 1. Mevcut durum ve kapsam

Depo incelemesiyle ölçülen başlangıç noktası:

| Alan | Dosya | Fiziksel satır |
| --- | ---: | ---: |
| Python presentation | 24 | 4.361 |
| Application | 21 | 1.710 |
| Domain | 10 | 847 |
| Infrastructure | 11 | 1.536 |
| Composition | 5 | 312 |

31 test dosyası ve 20 HTTP metot/rota çifti var. Satır sayıları yorum ve boş
satırları da içerir; iş yükü satır sayısından hesaplanmadı. `frontend/` ve
`src-tauri/` henüz yok. Node/npm PATH üzerinde bulundu; Rust araçları PATH
üzerinde bulunamadı. MSVC ve WebView2 kurulumu henüz doğrulanmadı.

Mevcut API; hesaplar, giriş işleri, League başlatma, ayarlar, otomasyon,
oyun durumu, şampiyon/kostüm listeleri, rün kataloğu/ikonları ve güncelleme
işlevlerini sunuyor. Eksikler: şampiyon portresi/kostüm görseli metadatası ve
önbelleği, önerilen rünü salt okunur önizleme, bazı sözlük yanıtlarının açık
tipli sözleşmelere dönüştürülmesi ve masaüstü servis yaşam döngüsü.

`run_app.py` Qt arayüzünü de başlattığından mevcut PyInstaller girişini doğrudan
Tauri yardımcı süreci yapmak uygun değil. Ayrı, arayüz açmayan backend girişi
gerekiyor. README'de geçen `installer/build_installer.ps1` depoda bulunmadı;
kurulum hattı hazır varsayılmadı.

**Dahil:** Windows x64, mevcut özelliklerin korunması, dört seçim ekranı,
hesap/giriş, ayar kaydı, tepsi/bildirim, Python paketleme, kurulum, güncelleme,
uyumluluk ve geçiş doğrulaması.

**Hariç:** telefon/PWA/QR eşleştirme, LAN veya internetten kontrol, macOS/Linux,
backend'i Rust ile yeniden yazma, yeni oyun otomasyonları, yeni veri scraper'ı,
canlı meta öneri servisi ve sınırsız tasarım revizyonu. Telefon fikri
[ana roadmap'te](../../ROADMAP.md) ertelenmiş kalır.

## 2. Hedef mimari ve geçiş ilkeleri

```text
React ekranları → tipli ApiClient / ApiTransport
  Geliştirme: izinli origin + oturum doğrulaması ile yerel HTTP
  Masaüstü: Tauri IPC → sınırlı Rust istek aracısı
                            ↓
                Uygulamaya ait FastAPI yardımcı süreci
                127.0.0.1 + dinamik port + geçici oturum anahtarı
                            ↓
                Mevcut application/domain/ports/adapters
                            ↓
                         Riot / LCU
```

- Oyun, rün doğrulama, ayar migrasyonu, hesap şifreleme ve giriş kuralları
  Python tarafında kalır. Rust; pencere, süreç ve masaüstü entegrasyonunu yönetir.
- Tauri, paketlenmiş Python API sunucusunu yardımcı süreç olarak çalıştırabilir.
  Hedef platform adlandırması ve çalıştırma izinleri paketleme işine dahildir.
  [Tauri sidecar belgesi](https://v2.tauri.app/develop/sidecar/)
- Önerilen yeni giriş `backend_main.py`; kendi PyInstaller tanımı olacak.
  Kullanıcının Python veya Node kurması gerekmeyecek. Tauri'nin küçük kabuk
  boyutu, Python içeren toplam uygulama boyutu için vaat olarak kullanılmayacak.
- Ana süreç geçici erişim anahtarı üretir; komut satırı argümanlarına/loglara
  yazmadan stdin veya ortam üzerinden aktarır. Üretimde anahtar Rust tarafında
  tutulur. Hazır olma mesajı yalnızca protokol sürümü/port gibi bilgileri taşır.
- Başlangıç zaman aşımı, çökme, sürüm uyuşmazlığı ve kapanış protokolü açıkça
  tanımlanır. Önce ayarlar kaydedilir, sonra servis durur. Zorunlu sonlandırma
  yalnızca uygulamanın başlattığı sürece uygulanır; porttaki başka süreç öldürülmez.
- CORS kimlik doğrulama yerine geçmez. Geliştirmede origin listesi dar tutulur;
  üretimde IPC komutları, hedef API yolları ve CSP sınırlandırılır. Genel shell
  çalıştırma veya kullanıcıdan gelen keyfi URL'lere erişim açılmaz.
- İlk sürüm mevcut sorgulama/polling yaklaşımını kullanır; WebSocket geçişi
  zorunlu kapsam değildir. Gerçek profil üzerinde Qt ve React aynı anda yazmaz;
  geliştirme doğrulamaları ayrı test profilleriyle yapılır.
- Qt, kabul ölçütleri tamamlanana kadar varsayılan ve geri dönüş seçeneğidir.
  Mevcut kullanıcı ayarları, hesap kimlikleri ve şifre çözme bağlamı korunur.

## 3. Fazlar ve tahmin

Saatler bir deneyimli geliştiricinin kişi-saatidir. Her faz geliştirme,
özelliğe özgü anlamlı testler ve gözden geçirmeyi içerir. P9 ayrıca bütünleşik
ürünü ve temiz makineyi doğrular; aynı test işi ikinci kez hesaplanmaz.

| Faz | İş paketi | İyimser | Olası | Kötümser | Bağımlılık |
| --- | --- | ---: | ---: | ---: | --- |
| P0 | Keşif ve teknik doğrulama | 8 | 12 | 20 | — |
| P1 | UX ve tasarım sistemi | 12 | 18 | 28 | P0 |
| P2 | React, API istemcisi ve ayar yönetimi | 20 | 28 | 40 | P0, P1 |
| P3 | Şampiyon ve ban ekranı | 20 | 28 | 40 | P2 |
| P4 | Rün editörü ve presetler | 20 | 28 | 44 | P2, P3 |
| P5 | Kostüm galerisi | 12 | 18 | 28 | P2, P3 |
| P6 | Hesap ve giriş ekranları | 16 | 24 | 36 | P2 |
| P7 | Tauri ve Python servis yaşam döngüsü | 24 | 36 | 56 | P0, P2, P6 |
| P8 | Kurulum ve güncelleme | 16 | 28 | 44 | P7 |
| P9 | Uçtan uca doğrulama ve geçiş | 16 | 28 | 44 | P3–P8 |
| **Toplam** | **10 paket / 45 alt görev** | **164** | **248** | **380** | |

Hesap: her faz için `E = (iyimser + 4 × olası + kötümser) / 6`.
Yuvarlanmamış değerler toplamı **256 saat**; %25 ortak belirsizlik payı **64
saat**; plan bütçesi **320 saat = 40 kişi-gün** (8 saat/gün). Belirsizlik payı
fazlara ikinci kez eklenmez. Bu senaryolar istatistiksel güven aralığı değildir.
[Makineyle okunabilir hesap](ui-modernization-estimate.json)

### P0 — Keşif ve teknik doğrulama · 4 görev

- [ ] P0.1 Node/Rust/MSVC/WebView2 ortamını doğrula; desteklenen sürümleri ve kilit dosyası politikasını belirle.
- [ ] P0.2 Mevcut davranışları, API sözleşmelerini ve eski profil örneklerini test verileriyle envanterle.
- [ ] P0.3 Minimal Tauri penceresi + paketlenmiş, arayüzsüz Python `/health` denemesi yap; başlatma/kapanışı doğrula.
- [ ] P0.4 Mimari karar kaydı oluştur; taşıma protokolü, sürüm eşleşmesi ve teknik yapılabilirliği karara bağlayıp tahmini güncelle.

**Kabul:** küçük prototip Python kurulmamış bir Windows test ortamında başlar,
sağlık yanıtı verir ve geride süreç bırakmadan kapanır. Tasarım öncesinde yerel
paketleme riski görülür. Windows araç önkoşulları
[resmî belgede](https://v2.tauri.app/start/prerequisites/) açıklanır.

### P1 — UX ve tasarım sistemi · 4 görev

- [ ] P1.1 Şampiyon/ban, rün, kostüm ve hesap akışlarının yerleşimlerini; küçük pencere/DPI davranışını tasarla.
- [ ] P1.2 Renk, tipografi, boşluk, kart, buton, odak ve yükleniyor/boş/hata durumlarını ortaklaştır.
- [ ] P1.3 Gerçekçi örnek verilerle tıklanabilir tasarım hazırla.
- [ ] P1.4 Bir geri bildirim turunu uygula; klavye ve farklı boyutlarda okunabilirlik kontrolünü tamamla.

**Kabul:** kullanıcı rol → seçim → rün → kostüm akışını prototipte tamamlar;
uygulama sırasında ekran başına yeni tasarım dili üretilmez.

### P2 — React, API istemcisi ve ayar yönetimi · 5 görev

- [ ] P2.1 React/TypeScript/Vite projesini, derleme/lint komutlarını ve bağımlılık kilitlerini kur.
- [ ] P2.2 Açık API yanıt modelleri ve OpenAPI tabanlı tipli istemciyi, ortak `ApiTransport` arayüzünü oluştur.
- [ ] P2.3 Ayar yükleme, sıralı/birleştirilmiş gecikmeli kayıt, değişiklik takibi ve kapanışta son kaydı uygula.
- [ ] P2.4 Önbellek, ortak istek paylaşımı, eski yanıtları yok sayma ve bulunamayan kayıtlı kimlikleri koruma davranışını kur.
- [ ] P2.5 Geliştirme erişimini origin/oturum ile sınırla; ayrı test profili ve aynı profile tek arayüz yazarı kuralını uygula.

**Kabul:** ayarlar yüklenemezse varsayılanlar kaydedilmez; katalog/ayar geliş
sırası sonucu değiştirmez; eski yanıt yeni düzenlemeyi ezmez; başarısız son kayıt
kapanışı durdurur. Ayar güncellemesi hesapları ve başka sahiplerin alanlarını korur.

### P3 — Şampiyon ve ban ekranı · 4 görev

- [ ] P3.1 Backend'de portre/varlık metadatasını ve ortak güvenli görsel önbellek altyapısını ekle.
- [ ] P3.2 Arama ve görünür öğe odaklı listeleme içeren portre kartlarını; seçim/ban için uygun sahiplik filtrelerini geliştir.
- [ ] P3.3 Beş rol, rol başına üç sıralı seçim ve ban düzenini kur; eksik kimlikleri ve kayıtlı seçim sırasını koru.
- [ ] P3.4 İki büyü seçimini, roller arası tutarlılığı ve klavyeyle sıralama/erişim davranışını tamamla.

**Kabul:** mevcut tüm seçimler kayıpsız açılır/kaydedilir. Aynı şampiyonun
kayıtlı tekrarı sessizce silinmez. Sınıf etiketlerinden varsayımsal koridor
önerileri üretilmez; ek rol verisi bu kapsama dahil değildir.

### P4 — Rün editörü ve presetler · 4 görev

- [x] P4.1 Ana/ikincil ağaç, dokuz perk ve nitelik parçalarını backend kurallarıyla uyumlu görselleştir.
- [x] P4.2 Şampiyon başına üç preset için oluşturma/düzenleme/silme ve önerilen rün seçimini uygula.
- [x] P4.3 Mevcut `RuneService` verisini kullanan salt okunur önerilen rün önizleme endpointini ekle.
- [x] P4.4 Geç gelen ikonların düzenlemeyi sıfırlamamasını; uygula/iptal/kapat ve hata davranışını doğrula.

28 Ekim: React rün editörü ve katalog tabanlı doğrulama tamamlandı. Kayıtlar
mevcut ETag/sıralı ayar yolunu kullanır. Açık rün taslakları kaydet/geri al
eylemi bekler; ekran/şampiyon/preset geçişinde korunur. Hata, eski okunamayan
preset, ikon hatası ve kontrollü çıkış tarayıcı testleriyle doğrulandı. Canlı
League'den beş ağaç ve ikonlar yalnızca okunarak kontrol edildi; gerçek maçta
otomatik uygulama için elle kabul testi hâlâ gereklidir.

**Kabul:** nitelik parçalarında kurallara uygun tekrarlar engellenmez; tüm dokuz
kimlik için genel benzersizlik şartı konmaz. Aynı şampiyonun presetleri roller
arasında ortaktır. Eski kayıt dönüşümleri backend'de kalır. Öneriler mevcut
paketlenmiş veriyi kullanır; güncel meta verisi vaadi eklenmez.

### P5 — Kostüm galerisi · 4 görev

- [x] P5.1 Sahip olunan kostümler ve varsayılan kostüm için kart tabanlı galeri oluştur.
- [x] P5.2 Bilinen kostüm kimliklerinden görsel çözümleme/önbellek, geç yükleme ve yedek görsel davranışını ekle.
- [x] P5.3 Seçimi ayarlara bağla; şampiyon değiştiğinde önceki kostüm isteğinin sonucunu yok say.
- [x] P5.4 Görsel yükleme performansını, önbellek sınırlarını ve galeri etkileşimlerini doğrula.

28 Ekim: Galeri mevcut sahiplik sorgusunu ve rol/şampiyon bazlı `custom_skins`
kaydını kullanır. Yerel League metadata'sından JPEG/PNG çözülür; 3 MiB/görsel,
32 MiB toplam, 32 görsel ve 32 şampiyon metadata önbelleği sınırı vardır. İlk
görsel hemen, kartlar geç yüklenir. Gerçek Teemo koleksiyonu ve JPEG görselleri
profil değiştirilmeden okundu; yazmalar ve canlı otomasyon güncellemeleri sahte
backend üzerinde doğrulanır. Gerçek maçtaki otomatik uygulama elle kabul bekler.

**Kabul:** sahip olunmayan kostüm seçilemez; eksik görsel seçimi bozmaz; keyfi
URL indiren endpoint açılmaz. Görsel kaynağının sürüm/erişilebilirlik durumu P0'da
doğrulanır; uygun olmayan kaynakta görselsiz yedek arayüz çalışır.

### P6 — Hesap ve giriş ekranları: kaldırıldı

10 Kasım 2026 kullanıcı kararıyla bu faz iptal edildi ve daha önce
uygulanan hesap/giriş kodları silindi. React/Qt doğrudan yapılandırmayı
açar. Eski hesap API yolları 404 döner; mevcut/eski profil ve staged kayıtlardaki
hesap alanı oyun ayarları korunarak temizlenir. Bu fazın eski saat tahminleri
aktif kalan iş olarak kullanılmaz.

### P7 — Tauri ve Python servis yaşam döngüsü · 6 görev

- [ ] P7.1 Dinamik loopback portu, hazır olma/sürüm protokolü ve sahip olunan süreç kapanışını üretim düzeyine getir.
- [ ] P7.2 Rust istek aracısı, geçici erişim anahtarı, CSP ve dar capability/komut izinlerini tamamla.
- [ ] P7.3 Tek uygulama örneği, sistem tepsisi, gizle/göster ve açıkça çıkış akışlarını taşı.
- [ ] P7.4 Kapanışı son ayar kaydına bağla; kayıt hatasında pencereyi açık tut ve sınırlı süreli servis kapanışını uygula.
- [ ] P7.5 Masaüstü bildirimlerini ve hassas veri içermeyen durum/hata tanılamasını ekle.
- [ ] P7.6 Arayüzsüz backend girişini/PyInstaller paketini tamamla; Qt GUI girişine bağımlılığı kaldır.

**Kabul:** port çakışması, çift açılış, backend çökmesi, tepsiden çıkış ve kayıt
hatası denenir; kullanıcı verisi kaybolmaz ve yetim otomasyon süreci kalmaz.

### P8 — Kurulum ve güncelleme · 5 görev

- [ ] P8.1 Windows x64 NSIS kurulumu ve frontend/backend sürüm eşleşmesini oluştur.
- [ ] P8.2 İmzalı Tauri güncelleme paketleri, metadata ve anahtar yönetimini kur; eski Python güncelleyicisiyle çift çalışmayı önle.
- [ ] P8.3 Mevcut kurulumdan geçişi, AppData profilini ve hesap şifre çözme uyumluluğunu koru.
- [ ] P8.4 Tekrarlanabilir derleme/CI, kilitli bağımlılıklar ve sürüm varlıklarını hazırla.
- [ ] P8.5 Python/Node olmayan temiz Windows ortamında kurulum, yükseltme ve kaldırmayı doğrula.

**Kabul:** tek paket kurulur ve yükselir; farklı backend sürümüyle sessizce
çalışmaz; güncelleme başarısızlığı mevcut profili bozmaz. İmzalı otomatik
güncelleme hazır olana kadar elle güncelleme kullanılır. Mevcut GitHub `.exe`
indirme akışı, Tauri imzalı güncellemesiyle aynı protokol değildir.
[Windows kurulum seçenekleri](https://v2.tauri.app/distribute/windows-installer/),
[zorunlu updater imzası ve metadata](https://v2.tauri.app/plugin/updater/).
Updater imzası ile Windows Authenticode kod imzası ayrı işlerdir; sertifika
satın alma/tedarik bekleme süresi bu mühendislik hesabına dahil değildir.

### P9 — Uçtan uca doğrulama ve geçiş · 5 görev

- [ ] P9.1 Ekranlar arası veri kaybı, bağlantı kopması ve yanıt sırası yarışları için bütünleşik senaryoları doğrula.
- [ ] P9.2 Gerçek Riot/LCU ile kapalı/açık client, oturum yok/var, 2FA ve ilk hesap EULA durumlarını elle dene.
- [ ] P9.3 DPI, pencere boyutu, klavye erişimi, açılış ve görsel önbellek performansını P0/P1'de belirlenen ölçütlerle ölç.
- [ ] P9.4 Sınırlı beta, profil yedeği ve sürümle uyumlu geri dönüş provasını tamamla.
- [ ] P9.5 Kabul ölçütleri geçince varsayılan başlatıcıyı ve belgeleri değiştir; doğrulanan geri dönüş süresi boyunca Qt yolunu koru.

**Kabul:** yalnızca sahte LCU testleriyle yayın kararı verilmez. Tam kullanıcı
akışı temiz makinede ve gerçek client ile geçer; eski ayar/hesaplar kayıpsızdır;
kurulum/güncelleme/geri dönüş denenmiştir. Qt kaldırma ayrı, sonraki karardır.

## 4. Roadmap ve teslim noktaları

Aşağıdaki saatler **başlangıçtan itibaren birikimli**, belirsizlik payı dahil
değerlerdir; satırlar birbirine eklenmez. Yuvarlama yalnızca son aşamada yukarı
yapılır. Takvim, haftada 30–35 net saat ve tek geliştirici varsayar.

| Teslim | Kapsam | Birikimli bütçe | Yaklaşık takvim |
| --- | --- | ---: | --- |
| M1 | P0–P1: teknik deneme ve tıklanabilir tasarım | 40 saat | 1–2 hafta |
| M2 | P0–P5: gerçek API ile dört seçim ekranı, tarayıcı geliştirme sürümü | 171 saat | 5–6 hafta |
| M3 | P0–P7: hesaplar, tepsi ve yardımcı süreç dahil Windows beta | 249 saat | 7–9 hafta |
| M4 | P0–P9: kurulum, güncelleme ve doğrulanmış tam geçiş | 320 saat | 9–11 hafta |

M2 tek başına kurulabilir masaüstü sürümü değildir; hesap/giriş ve yerel kabuk
paritesi M3'tedir. M3 de dağıtım/güncelleme doğrulaması tamamlanmış yayın değildir.
Bağımlılıklar izin verdiğinde P4/P5/P6 işleri farklı sırada yapılabilir; takvim
birden fazla geliştiricinin paralel çalışmasını varsaymaz.

40 saatlik haftanın tamamı net projeye ayrılsa teorik süre 8 haftadır. Gerçekçi
takvimde geri bildirim ve günlük işler için net 30–35 saat kullanıldı. Yalnızca
haftada 15 saat ayrılırsa aynı kapsam yaklaşık 22 haftaya çıkar. Yapay zekâ
desteği kod yazmayı hızlandırabilir; temiz makine, gerçek client, tasarım geri
bildirimi ve sürüm doğrulamasını ortadan kaldırmaz.

## 5. Riskler, sınırlar ve yeniden tahmin

| Risk | Etkisi ve karşılığı |
| --- | --- |
| Rust/MSVC/WebView2 veya Python paketleme uyumsuzluğu | P0'da erken paketli deneme; çözüm maliyeti belli olmadan tüm UI'yi taşımama |
| Qt davranışlarının eksik taşınması | P0 davranış matrisi, P2 veri kaybı testleri, P9 parite kapısı |
| Riot oturum/League/EULA akışının değişmesi | Backend kuralları korunur; gerçek client matrisi ve belirsizlik payı kullanılır |
| Portre/kostüm kaynaklarının değişmesi | Bilinen kimlikler, sürümlü önbellek ve görselsiz yedek; yeni scraper kapsam dışı |
| Python yardımcı sürecinin boyutu/başlangıcı | P0 ve P7'de ölçüm; minimal kabuk boyutuna dayanarak vaat vermeme |
| Güncelleme anahtarları ve Windows imzası | P8'de ayrı sorumluluklar; sırlar depoya girmez, sertifika/harici bekleme ayrı |
| Yeni özellik veya çoklu tasarım turu | Bu tahmine eklenmez; kapsam değişikliği olarak yeniden hesaplanır |

%25 pay; entegrasyon, paketleme ve davranış belirsizlikleri içindir. Yeni ürün
kapsamını karşılayan sınırsız bir bütçe değildir. P0, M2 ve M3 sonunda kalan iş
yeniden tahmin edilir. 9–11 hafta kesin olasılık aralığı olarak yorumlanmamalıdır.

**Parasal hesap:** `320 × üzerinde anlaşılan saatlik ücret + harici giderler`.
Saatlik ücret bilinmediği için para cinsinden bütçe uydurulmadı. İmza sertifikası,
CI/hosting ücretleri, indirme/tedarik beklemeleri ve kullanıcı geri bildirimini
bekleme süreleri ayrı kalemlerdir. İşletim gideri güncelleme dağıtım tercihine
göre P8'de netleşir.

## 6. İlk uygulama adımı

P0 ile başla: mevcut davranış ve örnek profil listesini çıkar; araç zincirini
doğrula; tek pencereden paketli Python sağlık yanıtı alıp düzgün kapatan küçük
denemeyi tamamla. P0.4 kararı sonrası P1 tasarımını, ardından P2–P3 ile ilk
gerçek şampiyon/ban ekranını geliştir. Bu belge hiçbir bağımlılık kurmaz,
uygulama girişini değiştirmez veya sürüm yayımlamaz.
