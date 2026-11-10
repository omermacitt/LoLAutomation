# RunePilot — Yol Haritası

## Modern masaüstü arayüzü

- **Durum:** React seçim ekranı, kayıt/otomasyon bağlantıları, rün editörü ve kostüm galerisi uygulandı. Hesap/giriş özelliği 10 Kasım'da kaldırıldı; masaüstü geçişi sürüyor.
- **Plan güncellemesi:** 10 Kasım 2026.
- **Yapı:** React + TypeScript + Vite, Tauri 2 masaüstü kabuğu, mevcut Python/FastAPI backend.
- **Detay:** [Uygulama planı, kabul ölçütleri ve iş yükü](docs/plans/ui-modernization.md).
- **Önceki geniş kapsam hesabı:** [Tarihsel tahmin verisi](docs/plans/ui-modernization-estimate.json); aktif ekran teslim süresi değildir.

| Sıra | Teslim noktası |
| --- | --- |
| 1 | React tema/iskeleti ve gerçek API'ye bağlı ilk şampiyon/ban ekranı |
| 2 | Seçim, büyüler, ayar kaydı ve otomasyon başlat/durdur akışının tamamlanması |
| 3 | Rün editörü ve kostüm galerisi |
| 4 | Temel Tauri masaüstü çalıştırması |

Kurulum, imzalı otomatik güncelleme ve tam dağıtım doğrulaması sonraki ayrı
aşamadır; ilk ekranların önkoşulu değildir. İlk gerçek ekran ve erken Tauri
denemesi sonrası kalan iş yeniden tahmin edilecek. Qt geri dönüş yolu korunur.
Telefon kontrolü bu kapsamın dışındadır.

### 28 Ekim ilerlemesi

`frontend/` altında tema, rol/seçim/ban, öncelik sıralaması, arama/sayfalama,
büyüler ve oyun/rol tercihleri hazır. Kalıcı ayar kaydı, son kaydı bekleyen
Başlat, Durdur, çalışan ayarını güncelleme ve kontrollü oturum bitirme bağlandı.
[Çalıştırma ve tarayıcı çıkış sınırları](frontend/README.md).

Derleme, 350 Python testi, 46 frontend testi ve 63 tarayıcı kontrolü geçti;
canlı kontrollerin diğer pencere boyutlarındaki altı tekrarı atlandı. Gerçek ayar
okuma ve ETag doğrulandı. Yazma/otomasyon akışları geçici test verileri ve sahte
backend ile sınandı. Canlı katalog (173 normal şampiyon) ve portreler doğrulandı.
League Classic varyantları ayıklandı. Sayfalama üç dolu satıra uyarlandı;
11 sütunda 33 kart ve yeniden boyutlandırma kontrol edildi. Gerçek oyun içi
uygulama senaryosunun elle doğrulanması bekliyor.

Aynı rolün tercihlerinde bir şampiyon yalnızca bir kez kullanılabilir. Kart,
seçim modeli, kayıt ve otomasyon katmanlarında kural uygulandı. Eski tekrarlar
ilk tercih korunarak boş slotlara dönüştürülür; diğer rollerde yeniden kullanım serbesttir.

Rün editöründe ana/ikincil ağaçlar, nitelik parçaları ve şampiyon başına üç ortak
preset hazır. Güncel League kataloğuyla doğrulama, açık kayıt/silme/seçme,
taslak koruma ve mevcut veri paketinden öneri önizlemesi bağlandı. Gerçek rün
ikonları doğrulandı; canlı kontrolde profil değiştirilmedi.

Kostüm galerisi varsayılan ve sahip olunan kostümleri gerçek League görselleriyle
gösterir. Rol/şampiyon bazlı seçim, varsayılana dönüş, arama ve otomatik kayıt
bağlandı. Geç yanıt, eksik görsel, kayıtta hata ve artık bulunmayan eski seçim
durumları korunuyor. Görsel önbelleği boyut ve adetle sınırlı. Canlı JPEG görselleri
ve koleksiyon okuması profili değiştirmeden doğrulandı. Sonraki geliştirme hesap/giriş
ekranları ve masaüstü kabuğu. Tauri henüz eklenmedi.

### 29 Ekim rün kaydı düzeltmesi

Tarayıcı çevirisinin düğme metnine müdahalesi sırasında kayıt sonrası oluşan
`insertBefore`/siyah ekran hatası yeniden üretildi ve simge/metin kapsayıcıları
sabitlenerek giderildi. Beklenmeyen görüntüleme hatalarına yeniden yükleme ekranı
eklendi. 48 frontend testi, 67 tarayıcı kontrolü ve üretim derlemesi geçti;
canlı testlerin diğer boyutlardaki sekiz tekrarı atlandı. Gerçek profil korunarak
üç preset kaydı profil kopyasında da doğrulandı.

### 29 Ekim seçim güvenliği ve UX incelemesi

Autofill boş havuz ve bütün adayların banlı/alınmış olması için manuel devir
uygulandı. Oyun/seçim turu kullanıcıya bırakıldıktan sonra havuz değişikliği
otomatik kilitlemeyi geri başlatmaz; manuel hover ve kilitli seçim korunur.
Üçüncü tercihe geçiş, gerçek seçilen şampiyonun ayarları ve ilk tercihin yanlış
büyülerini aktarmama test edildi. Ana/ikincil rol zorunluluğu korunurken diğer
rollerin eksikleri autofill uyarısına dönüştürüldü. Bildirim sayfalar arasında
görünür kalır; ses engeli, sessize alma/Durdur yarışı ve bağlantı kaybı ele alındı.

Kullanıcının talebiyle ayrı UX test agent'i çalıştırıldı. Kalıcı rol talimatı
[UX Tester](.agents/ux-tester.md), senaryolar ve bağımsız bulgular
[UX senaryoları](docs/qa/ux-scenarios.md) içindedir. Gerçek maç testi yapılmadı.
360 Python testi, 54 frontend testi, 73 tarayıcı kontrolü ve derleme geçti;
sekiz canlı test tekrarı atlandı. UX agent'i masaüstü/mobil Mid/ADC→Jungle
akışını bağımsız olarak da doğruladı.

### 29 Ekim hesaplar ekranı — tarihsel, 10 Kasım'da kaldırıldı

Hesap ekleme/düzenleme/kaldırma, silme onayı, parola koruma ve Riot giriş akışı
React'e taşındı. Girişten önce son ayar kaydı ve otomasyon Stop doğrulanır;
kaydedilmemiş hesap/rün taslakları hesap geçişini engeller. UUID işi ekranlar
arasında korunur, sayfa yenilenince aktif iş bulunur. Belirsiz kayıt yanıtları
otomatik tekrar edilmez. CAPTCHA/2FA, EULA, League devamı ve girişsiz devam
gösterilir. Hesap geçişinde açık kostüm/rün kaynakları yenilenir.

Mevcut Python hesap servisi, atomik profil deposu ve şifreleme korunur. Gerçek
hesap kaydı/girişi bu geliştirmede denenmedi; testler sentetik hesaplarla çalışır.
Tauri kabuğu ve native paketleme sonraki aşamada kalır.

360 Python testi, 68 frontend testi, 88 tarayıcı kontrolü ve üretim derlemesi
geçti; sekiz canlı test tekrarı atlandı. Hesap akışları üç pencere genişliğinde
taklit API ile doğrulandı.
Son UX iyileştirmeleriyle Hesaplar için 18 kontrol, bağımsız agent turunda da
masaüstü/390 px'de 12 kontrol geçti.

### 10 Kasım hesap özelliğinin kaldırılması

Kullanıcının güvenlik tercihiyle React ve Qt hesap ekranları, hesap/giriş/League
başlatma HTTP yolları, parola şifreleme ve Riot otomatik giriş kodları kaldırıldı.
Masaüstü doğrudan yapılandırmayı açar. Riot Client girişi ve League'i başlatma
kullanıcı tarafından yapılır; sonraki katalog/sahiplik verileri Yenile ile okunur.

Backend açılışındaki geçiş mevcut/eski profiller ve `.tmp` kayıtlarından yalnız
`accounts` alanını siler. Gerçek iki profilin oyun ayarları hash ile aynı kaldı;
hesap alanlarının kalmadığı doğrulandı. Parola içeren yedek oluşturulmaz.

245 Python testi, 54 frontend testi, 73 tarayıcı kontrolü ve üretim derlemesi
geçti; canlı veri testlerinin diğer pencere boyutlarındaki sekiz tekrarı atlandı.

## Telefondan League kontrolü

- **Durum:** İleri aşamalara ertelendi. Şu anda uygulanmayacak.
- **Not tarihi:** 27 Ekim 2026.
- **Referans:** [Instagram paylaşımı — League Companion](https://www.instagram.com/p/De7RIdzI09Y/).
- **Ek kaynak:** [League Companion çalışma akışı](https://leaguecompanion.com/how-it-works.html).

### Amaç

RunePilot açık olan bilgisayardaki League istemcisini telefondan yönetebilmek.
İlk fikir yalnızca görsel tasarım değil, mobil kontrol ve masaüstü eşleştirmesidir.

### Değerlendirilecek kapsam

- Telefonu bilgisayarla QR kod üzerinden eşleştirme ve bağlantıyı iptal edebilme.
- Lobi, kuyruk, hazır kontrolü ve şampiyon seçimi durumlarını canlı gösterme.
- Kuyruk başlatma/durdurma ve maç kabul etme.
- Şampiyon pick/ban, büyü ve rune seçimlerini telefondan yönetme.
- Maç bulunduğunda veya oyun başladığında telefona bildirim gönderme.

### Mevcut projeyle bağlantısı

FastAPI backend'i, `LeagueClient` portu ve mevcut LCU adapter'ı yeniden kullanılabilir.
Mobil ekranlar için canlı durum aktarımı ve ayrı komut use case'leri gerekir.
Telefonun verdiği seçimlerle mevcut otomatik seçim döngüsünün çakışmasını önleyen
bir kontrol modu tasarlanmalıdır.

Telefon erişimi yalnızca izin verilen oyun işlemlerini kapsamalı; Riot parolaları,
LCU kimlik bilgileri ve güncelleme işlemleri masaüstünde kalmalıdır. Kaldırılmış
hesap yönetimi veya parola saklama bu fikir kapsamında geri eklenmeyecek.
Mevcut yerel API'yi doğrudan dış ağa açmak yerine eşleştirilmiş cihazlara yönelik
ayrı bir erişim sınırı kurulmalıdır.

### Henüz kararlaştırılmayanlar

- Yalnızca aynı Wi-Fi üzerinden mi, yoksa ev dışından da erişim mi sağlanacağı.
- Mobil web/PWA ile mi başlanacağı, yoksa native mobil uygulama mı geliştirileceği.
- İlk sürümün kesin özellik kapsamı ve internet erişimi istenirse relay altyapısı.

Bu konu tekrar ele alındığında önce bu kararlar netleştirilecek, ardından küçük
bir ilk sürüm planlanacak. Henüz entegrasyon veya ağ erişimi etkinleştirilmedi.
