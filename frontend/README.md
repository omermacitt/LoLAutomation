# RunePilot React arayüzü

React + TypeScript + Vite ile masaüstü arayüzünün geliştirme sürümü. Şampiyon/ban
seçimi, seçim sırası, büyüler, rün editörü, kostüm galerisi, kalıcı kayıt ve otomasyon kontrolleri hazır.
Tauri 2 masaüstü kabuğu ve Windows beta Setup üretimi eklendi; temiz makine ve
gerçek League kabulü bekliyor. [Derleme ve dağıtım](../README.md#build-the-windows-desktop-installer).

## Çalıştırma

Node 22.12 veya üstü ve mevcut projenin Python bağımlılıkları gerekir.
Proje kökünde backend'i başlat:

```powershell
.\.venv\Scripts\python.exe main.py
```

İkinci terminalde:

```powershell
cd frontend
npm ci
npm run dev
```

Arayüz: <http://127.0.0.1:5173>. Backend: <http://127.0.0.1:8000>.
Bu adım backend'de yeni endpoint ve ETag desteği içerir; daha önce açılmış
`main.py` sürecini güncel kodla yeniden başlat. Şampiyon kataloğu için League
istemcisinin açık ve yanıt veriyor olması gerekir. Bağlantı yoksa hata/yeniden
deneme görünür; sahte katalog kullanılmaz. Ayarlar ve katalog yüklenmeden
düzenleme/başlatma etkinleşmez; yükleme hatası boş ayarlarla kaydedilmez.

Vite yalnızca loopback üzerinde çalışır. Proxy sadece izinli yolları/metotları
aktarır: sağlık/katalog/ayar okuma, kostüm listesi/görsel okuma, rün kataloğu/öneri/ikon okuma ve doğrulama,
ayar kaydı, başlat/durdur ve çalışan ayarı güncelleme. Yazmalarda bellekte
tutulan geliştirme oturum anahtarı gerekir;
izinsiz origin, eksik anahtar ve diğer API yolları reddedilir. Backend'e genel
CORS izni eklenmedi. Tauri paketi Vite proxy'si kullanmaz; Rust özel backend
anahtarını tutar, izinli JSON isteklerini IPC ile, görselleri yerel protokolle aktarır.

Gerçek profili aynı anda yalnızca bir arayüzden düzenle. Qt başlangıç yolu
korunuyor. Aynı backend'deki güncel Qt/React istemcileri ETag ile eski kayıtların
üstüne yazılmasını engeller; başka backend süreçleri arasında dosya kilidi veya
tek uygulama örneği garantisi yoktur. Yeni Tauri kabuğu kendi ikinci örneğini engeller;
Qt veya ayrı geliştirme backend'lerini aynı profile paralel açma.

## Kullanılabilen akış

- Beş rol, üç öncelikli şampiyon, yukarı/aşağı sıralama, ban, arama ve sayfalama.
- Gerçek League portreleri havuzda ve seçimlerde gösterilir. Görseller geç
  yüklenir; yüklenemeyen portrede baş harfler korunur ve Listeyi yenile yeniden dener.
  Sayfa kapasitesi satıra sığan kart sayısının üç katıdır: 11 sütunda 33 kart.
  Son sayfa veya az sonuçlu arama dışında üç satır dolu kalır. Pencere boyutu
  değiştiğinde sayfa kapasitesi de değişir; kayıtlı seçimlere dokunulmaz.
- Aynı şampiyon bir rolün tercihlerinde yalnızca bir kez seçilir; farklı rollerde
  tekrar kullanılabilir. Başka bir tercihte kullanılan kart o rol içinde pasiftir
  ve hangi tercihte seçili olduğunu gösterir. Tercihi temizlemek şampiyonu serbest bırakır.
- Oyun modu, ana/ikincil rol ve her rol/şampiyon için iki farklı büyü.
- Değişiklikler 500 ms bekleyerek birleştirilir ve sırayla kaydedilir. Devam eden
  kaydın yanıtı sonraki düzenlemeyi ezmez. Hata taslağı korur; yeniden deneme veya
  kaydedilmemiş değişiklikleri geri alma mümkündür.
- Ayar kaydı, mevcut rün/kostüm alanlarını taşır; backend kaldırılmış hesap verisini
  temizler, diğer tercih alanlarını atomik olarak korur. Kaydedilmiş eksik şampiyon kimlikleri
  ve benzersiz eski satırlar korunur. Eski rol içi tekrarlarda ilk tercih tutulur,
  sonraki tekrarların yerleri boş bırakılır; sıra veya büyü/rün/kostüm ayarları
  değiştirilmez. Bu dönüşüm okuma sırasında dosyaya yazmaz; sonraki geçerli kayıt
  ile kalıcılaşır. Backend, yeni tekrarlı kayıt ve otomasyon isteklerini reddeder.
- Başlat son kaydı bekler; seçilen ana/ikincil roller için en az bir seçilebilir
  şampiyon ve bilinen ban gerektirir. Diğer eksik roller autofill uyarısıdır,
  Başlat'ı engellemez. İki rol de seçilmemişse tüm rol kontrolü korunur.
  Kaydetmek otomasyonu başlatmaz. Çalışan otomasyona
  güncellemeler yalnızca başarılı kayıttan sonra `PUT /automation/config` ile
  gider. Bu endpoint durdurulmuş otomasyonu başlatamaz.
- Durdur, bekleyen başlangıcı/ayar uygulamasını geçersiz kılar ve uçuşta bir
  başlangıç varsa ardından çalışır. Durum çalışırken saniyede bir, kapalıyken dört
  saniyede bir sorgulanır; eski bir
  sağlık yanıtı yeni komutun sonucunu ezmez. Kaybolan komut yanıtı körlemesine
  tekrarlanmaz; durum yeniden sorgulanır.

**Kayıt çakışması:** GET/PUT `/settings` bir ETag döndürür; istemci PUT isteğinde
`If-Match` gönderir. Başka pencere aynı ayarları değiştirmişse 412 döner ve taslak
korunur. “Yerel değişiklikleri bırak ve yeniden yükle” bilinçli olarak sunucudaki
ayarları alır. Diğer tercih alanları ayar sürümünü etkilemez. Başarılı olup yanıtı
kaybolmuş bir kayıt, yeniden denemeden önce sunucudan doğrulanır.
[If-Match davranışı](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/If-Match)

## Autofill, yedek tercihler ve manuel seçim

Atanan rolün tercihleri sırayla denenir; banlı, alınmış veya seçilemeyen şampiyon
atlanır. Başka rolün tercihleri autofill rolüne taşınmaz. Boş rol havuzu, bütün
adayların tükenmesi veya başarısız kilitleme durumunda o oyun/seçim turu kullanıcıya
devredilir. Aynı turda havuz güncellense bile otomatik kilitleme geri başlamaz.
Oyuncunun hover'ı veya kilitli şampiyonu değiştirilmez; sıra başlamadan pick isteği
atılmaz. Rastgele şampiyon kilitlenmez veya otomatik oyundan çıkılmaz.

`GET /health.selection` geçici `id/code/role/champion_id` bildirimi taşır; profilin
parçası değildir. Bildirim bütün sayfalarda sticky panelde görünür. Bir olayda
tek kısa ses denenir; tarayıcı engellerse görsel bildirim kalır ve **Uyarıyı dinle**
ile yeniden denenebilir. **Sesi kapat** ve **Otomasyonu durdur** geciken sesi de
iptal eder. Geçici bağlantı kaybında son manuel uyarı, doğrulanmış yeni durum gelene
kadar korunur. Şampiyon kilitlenince, oturum bitince veya otomasyon durunca temizlenir.

Manuel/yedek şampiyon için o şampiyonun kayıtlı rünü ve rol/kostüm/büyü ayarları
varsa uygulanır. İlk tercih şampiyonundan türetilmiş büyüler başka şampiyona
aktarılmaz; özel büyü kaydı yoksa mevcut istemci büyüleri korunur. Rün seçimi
gerçek atanan rol ve seçilen şampiyona göre çözülür; başka rolün ataması taşınmaz.

## Rün editörü

Sol menüde **Rünler** veya seçili şampiyonun altındaki **Rünleri düzenle** ile açılır.
Ana yolun dört satırı, farklı satırlardan iki ikincil rün ve üç nitelik parçası
League istemcisinin güncel kataloğundan gelir; ikonlar da aynı istemciden okunur.
Nitelik parçalarının farklı satırlardaki izinli tekrarları korunur.

Her şampiyon için roller arasında ortak üç preset vardır. **Preseti kaydet** önce
`POST /runes/validate` ile doğrular, sonra mevcut sıralı `/settings` kaydına katılır;
başarılı kayıt o preseti yalnız ekranda seçili role atar. Örneğin Volibear üst
koridorda Preset 1, orta koridorda Preset 2 kullanabilir. İçerik ortak olduğu için
bir preset'i düzenlemek onu kullanan diğer rolleri de etkiler; etkilenen roller
ekranda gösterilir. Silme o sayfayı kaldırır ve onu kullanan rol atamalarını açıkça
önerilene döndürür. Diğer preset, şampiyon, büyü ve kostüm alanları korunur.

Eski şampiyon bazlı seçim varsayılan olarak korunur. Rol ataması yoksa bu seçim
kullanılır. **Önerileni kullan** yalnız o role önerileni atar; **Varsayılanı kullan**
rol atamasını kaldırıp eski şampiyon seçimini devreye alır. Açık öneri seçimi eski
bir preset'e dönüşmez. Rün ekranı rol/şampiyon ve aktif seçimin kaynağını gösterir.

Autofill, yedek ve manuel şampiyonda gerçek maç rolü esas alınır. Rol bilgisi yoksa
eski şampiyon varsayılanı, o da yoksa veri paketindeki öneri kullanılır. Eksik veya
geçersiz bir role atanan preset yerine doğrulanmış öneri denenir; kullanılabilir
öneri veya katalog yoksa rün yazılmaz ve ayrı bir uyarı gösterilir. Bu uyarı manuel
şampiyon seçimi bildirimini silmez. Otomasyon özel/önerilen sayfayı oyun yazmasından
önce editörün güncel katalog kurallarıyla doğrular.

Rün formu açıkça kaydedilir; ekran, şampiyon veya preset değiştirirken yerel taslak
korunur. Kaydedilmemiş rün düzenlemeleri Başlat ve kontrollü çıkışı durdurur;
editörden kaydet veya geri al. Başarısız kayıt formu korur ve tekrar denenebilir.
Okunamayan eski preset kendiliğinden değiştirilmez; yeni sayfa hazırlamak veya
silmek kullanıcı eylemi gerektirir. İkon hatası seçimleri sıfırlamaz.

Önerilen sayfa mevcut `RuneService` veri paketinden salt okunur gösterilir;
bir presete kopyalanabilir. Eksik veya güncel katalogla uyuşmayan öneri belirtilir.
Canlı meta veya güncel kazanma oranı vaadi yoktur. Editörde kaydetmek League'e
hemen sayfa yazmaz; oyun içi uygulama mevcut otomasyonun şampiyon seçimi akışındadır.

Kayıt düğmesinin simgesi ve metni ayrı, sabit kapsayıcılarda tutulur. Tarayıcı
çevirisinin metni değiştirdiği durumda da kayıt tamamlanınca editör açık kalır.
Bu durum, kayıt sürerken metni `<font>` ile değiştiren bir tarayıcı testiyle
doğrulanır. Aynı hata türü [React'te de izlenmiştir](https://github.com/facebook/react/issues/11538).
Beklenmeyen bir görüntüleme hatasında boş ekran yerine yeniden yükleme ekranı
gösterilir; yeniden yükleme kaydedilmemiş düzenlemeleri kaybettirebilir ve çalışan
otomasyonu durdurmaz.

## Kostüm galerisi

**Kostümler** menüsünden veya seçili şampiyonun altındaki **Kostüm seç** ile
açılır. Şampiyon ve rol seçilir; varsayılan ve sahip olunan kostümler listelenir.
Seçili kostüm büyük önizlemede gösterilir. Arama yalnızca bu koleksiyonu filtreler.

Kart seçimi mevcut sıralı otomatik kayıt ve ETag akışını kullanır. `custom_skins`
altında yalnızca hedef rol/şampiyon değişir; rünler, diğer roller ve şampiyonlar
korunur. **Varsayılana dön** yalnızca o rol/şampiyonun özel seçimini kaldırır.
Kaydetmek otomasyonu başlatmaz; çalışan otomasyona başarılı kayıttan sonra iletilir.

Liste, `GET /champions/{id}/skins` ile gelir. Önceki şampiyona ait geç yanıtlar
yok sayılır. Katalog hatasında düzenleme durur; boş/default ayarlar kaydedilmez.
Kayıtlı kostüm artık listede yoksa kimliği korunur ve uyarı gösterilir.
Başarısız kayıtta yeni seçim korunur; ortak kayıt çubuğundan tekrar denenebilir.

`GET /champions/{id}/skins/{skinId}/artwork` yalnızca bilinen kostümün League
metadata'sındaki yerel görsel yolunu çözer; kullanıcı URL/path gönderemez. JPEG/PNG
kontrolü, görsel başına 3 MiB, toplam 32 MiB / 32 görsel sınırı ve beş dakikalık
önbellek uygulanır. Metadata en fazla 32 şampiyon için tutulur. Kart görselleri
geç yüklenir; görsel hatası şampiyon portresine döner ve seçimi engellemez.
**Kostümleri yenile** listeyi ve başarısız görselleri yeniden dener.

## Riot ve League'i açma

10 Kasım 2026'da hesap yönetimi ve otomatik giriş tamamen kaldırıldı. Riot Client'ı
açıp giriş yaptıktan sonra League'i kendin başlat. RunePilot doğrudan seçim
ekranını açar. Riot'ta elle hesap değiştirdiğinde şampiyon/rün/kostüm verilerini
ilgili **Yenile** düğmeleriyle tekrar yükleyebilirsin.

Eski hesap/giriş/League başlatma API yolları kapalıdır. Backend açılışında
mevcut/eski profil dosyalarındaki ve yarım kalmış `.tmp` kayıtlarındaki `accounts`
alanı temizlenir; diğer oyun ayarları korunur. Temizlik başarısızsa servis açık
bir hatayla başlamaz; hassas veri içeren yedek oluşturulmaz.

Kaldırma doğrulaması: 245 Python testi, 54 frontend testi, 73 tarayıcı kontrolü
ve üretim derlemesi geçti; canlı testlerin diğer genişliklerdeki sekiz tekrarı
atlandı. Menü/parola alanı yokluğu, eski API yollarının geçerli oturumla bile
404 vermesi ve normal seçim/kayıt/otomasyon akışları kontrol edildi.

## Çıkış davranışı

**Kaydet ve oturumu bitir** önce son kaydı, ardından otomasyonun durduğunu
doğrular. Başarısızlıkta oturum açık kalır ve değişiklikler korunur. Başarıda
pencerenin kapatılabileceği gösterilir. Tarayıcı, haricen başlatılan Python
sunucusunun sahibi değildir; bu düğme FastAPI sürecini sonlandırmaz.

Sekmeyi doğrudan kapatırken/yenilerken kaydedilmemiş veri, devam eden komut veya
çalışan/durumu bilinmeyen otomasyon varsa standart tarayıcı uyarısı istenir.
Tarayıcı kapanış olayında asenkron kaydın tamamlanması garanti edilemez; kullanıcı
uyarıyı geçerse veya süreç zorla kapanırsa kontrollü çıkış atlanabilir. Tauri
aşamasındaki native kapanış kapısı henüz uygulanmadı.
[Tarayıcı beforeunload sınırları](https://developer.mozilla.org/en-US/docs/Web/API/Window/beforeunload_event)

## Sonraki işler

Portreler ve kostüm görselleri mevcut League
istemcisinden alınır; harici görsel servisi gerekmez. Backend bilinen normal
şampiyonların PNG portrelerini sınırlı bellekte beş dakika önbellekler. Paketleme,
tepsi, güncelleme ve Tauri yardımcı süreç yaşam döngüsü sonraki aşamalarda.

## Kod yapısı

- `src/api/`: HTTP, yanıt doğrulaması, ETag ve geliştirme oturum anahtarı.
- `src/features/champions/`: seçim modeli, katalog ve ekranın koordinasyonu.
- `src/features/runes/`: ağaçlar, ortak presetler, yerel taslaklar ve rün kuralları.
- `src/features/skins/`: sahip olunan kostüm galerisi, görseller ve rol bazlı seçim.
- `src/features/settings/SettingsWriter.ts`: sıralı kayıt, birleştirme ve son kayıt.
- `src/features/automation/`: payload eşlemesi, durum sorgulama ve komut sırası.
- `src/components/`: seçim, büyü, oyun ayarı ve kayıt kontrolleri.
- `src/test/`, `e2e/`: yalnızca testlerde kullanılan örnek veriler/kontroller.

Dosya erişimi, eski kayıt migrasyonu, otomasyon ve Riot/LCU kuralları Python'da
kalır. UI profil dosyasını doğrudan okumaz/yazmaz; yanıt doğrulama hatası varsayılan
ayar üretmez. Profil verisi veya oturum anahtarı localStorage'a/loglara yazılmaz.

## Doğrulama

```powershell
npm run build
npm test
npm run test:e2e
```

Edge kurulu olmalıdır; tarayıcı testleri headless çalışır. 1440, 1024 ve 390 piksel
genişliklerde kayıt/yeniden açma, sıra/büyü, hata/çakışma ve başlat/durdur akışı
kontrol edilir. Yazmalar/oyun komutları sahte backend üzerinde sınanır. Canlı
şampiyon, rün ve kostüm kontrolleri çalışan backend/League gerektirir; gerçek profili
değiştirmez, giriş yapmaz ve otomasyonu başlatmaz. Şampiyon kontrolü backend
yoksa atlanır; rün ve kostüm kontrolleri açık League gerektirir.
Ekran görüntüleri `test-results/` altındadır.

Mock testleri gerçek maçta otomatik seçim/kilit veya fiziksel ses doğrulaması
sayılmaz. Gerçek League kabulü, kullanıcının yönettiği ayrı bir oturumda yapılır.

Grid ölçümü için [ResizeObserver](https://developer.mozilla.org/en-US/docs/Web/API/ResizeObserver)
kullanılır; yüklenme/boş/hata durumlarında da ölçüm alanı korunur.

`npm run preview` statik çıktıyı inceler; geliştirme API proxy'sini sağlamaz.
Gerçek API ile şimdilik `npm run dev` kullan.
