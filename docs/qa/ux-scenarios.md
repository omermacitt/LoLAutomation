# RunePilot kullanıcı deneyimi senaryoları

Rol tanımı: [UX Tester](../../.agents/ux-tester.md). İnceleme tarihi: 29 Ekim 2026.
Bu belge ilk senaryo setidir; bir kabul veya gerçek maç testinin geçtiği anlamına gelmez.
Gerçek profil ve oyun durumu değiştirilmez. Yazmalar/oyun eylemleri sahte backend ve LCU'da tutulur.

## Öncelikli kabul senaryoları

| Kimlik | Öncelik | Başlangıç ve eylem | Beklenen kullanıcı sonucu |
| --- | --- | --- | --- |
| UX-01 | P1 | Mid/ADC tercihli kullanıcıya Jungle atanır; Jungle havuzu boş. | Mid şampiyonu Jungle için kilitlenmez. Atanan rolü ve manuel seçim gereğini söyleyen görünür uyarı gelir. |
| UX-02 | P1 | Rol havuzunda Zed → Ahri → Orianna vardır; Zed banlanır. | Kullanılabilir Ahri seçilir; kayıtlı tercih sırası değişmez. |
| UX-03 | P1 | İlk tercih banlı, ikinci rakipte alınmış, üçüncü uygundur. | Üçüncü tercih seçilir; banlı/alınmış adaylar için kilitleme isteği gitmez. |
| UX-04 | P1 | Üç tercih de kullanılamaz; oyuncunun seçim sırası gelir. | Rastgele şampiyon seçilmez. Kullanıcı manuel seçime yönlendirilir; aynı uyarı her sorguda yeni olay gibi çalmaz. |
| UX-05 | P0 | UX-01/04 uyarısından sonra kullanıcı League'de farklı şampiyonu seçer. | Otomasyon kullanıcı seçimini değiştirmez. Uyarı güncelliğini kaybeder; son seçilen şampiyonun uygun ayarları kullanılır. |
| UX-06 | P1 | İkinci/üçüncü veya manuel şampiyon ilk tercihten farklıdır; özel büyü kaydı yoktur. | İlk tercih şampiyonunun büyüleri yanlışlıkla uygulanmaz; açık varsayılan davranış izlenir. |
| UX-07 | P1 | Kullanıcı Rünler veya Kostümler ekranındayken UX-01/04 oluşur. | Acil uyarı mevcut görünümde, kaydırma gerektirmeden fark edilir; yapılacak işlem nettir. |
| UX-08 | P1 | Tarayıcı sesi engeller, AudioContext yoktur veya ses kapalıdır. | Görsel uyarı ve sonraki eylem yine kullanılabilir; ses hatası ekranı/otomasyonu çökertmez. |
| UX-09 | P1 | Uyarı sürerken aynı sağlık yanıtı tekrar gelir; sonra yeni şampiyon seçimi oturumu başlar. | Eski olay tekrarlanmaz; yeni oturumdaki gerçek yeni olay yeniden bildirilebilir. |
| UX-10 | P1 | Kullanıcı Durdur'a basar veya şampiyon seçimi sona erer; eski yanıt geç gelir. | Eski uyarı/komut geri dönmez; otomasyon kendiliğinden başlamaz. |
| UX-11 | P1 | Kullanıcı havuz veya preset değiştirir; kayıt 500/412 döner. | Yerel düzenleme korunur; kayıt sonucu açık görünür. Değişiklik başarılı olmadan çalışan otomasyona uygulanmış gibi gösterilmez. |
| UX-12 | P2 | Yukarıdaki uyarılar 1440, 1024 ve 390 px genişlikte; klavye ile kullanılır. | Başlık/eylem taşmaz; odak görünürdür; yalnız renkle durum anlatılmaz; ekran okuyucu uyarıyı duyurur. |
| UX-13 | P1 | Kayıt sırasında sayfa çevirisi düğmenin metin düğümünü değiştirir. | Kayıt tamamlanır; siyah ekran oluşmaz; beklenmeyen hata olursa anlamlı kurtarma ekranı vardır. |

Yeni devir akışı için ek sınırlar:

- Oyuncunun pick action'ı `isInProgress=false` ise erken kilitleme veya acil
  manuel seçim uyarısı üretilmez. Gerçek sıraya geçildiğinde durum yeniden değerlendirilir.
- Aynı `gameId/actionId` için manuel devir verildikten sonra havuz değişmesi veya
  uyarının okunması otomatik kilitlemeyi geri getirmez. Kilitli seçim ve kullanıcının
  hover/intention bilgisi korunur.
- Sağlık yanıtındaki salt okunur seçim bildirimi eski/iptal edilmiş sorgu ile geri
  gelmez. Rol metni ve eylem anlaşılırdır; aynı bildirim kimliği tek kez ses verir.
- İlk tercih olmayan manuel/yedek şampiyonun özel büyüsü yoksa ilk tercihten
  türetilen rol/global büyüler yazılmaz. Eski API'nin açık rol/global varsayılanları
  ile yeni şampiyon havuzu verileri ayrılarak uyumluluk korunur.
- Ses engellenirse görünür metin ve isteğe bağlı elle ses düğmesi kalır. Bu düğme
  şampiyon seçmez, oyun penceresi açmaz, otomasyonu yeniden başlatmaz veya uyarıyı silmez.
- Manuel seçimden sonra uyarı güncelliğini kaybedip temizlenir; rün/kostüm uygulaması
  gerçekten seçilen şampiyona göre yapılır. Rün preset seçiminin rol ayrımı ayrıca geliştirilmedikçe vaat edilmez.

Örnek uyarı metni: **"Jungle için seçilebilir şampiyon kalmadı. LoL ekranında manuel seçim yap."**
"Durdur" ile "manuel şampiyon seçimi bekleniyor" aynı durum değildir. Manuel devirde
otomasyonun diğer görevlerinin sürüp sürmediği kullanıcıya açıkça anlatılmalıdır.

## İlk kaynak incelemesi — uyarı akışı geliştirilmeden önce

Bu bulgular kaynakta görülen davranışlardır; bu incelemede tarayıcıda veya gerçek maçta yeniden üretilmediler.

| Kimlik | Önem | Kaynakta gözlenen durum | Etki ve öneri |
| --- | --- | --- | --- |
| F-01 | P1 | `AutomationRunner` atanan rol havuzu boşsa seçim çağrısını atlıyor; `all_unavailable` sonucu kullanıcıya taşınmıyor. | Kullanıcı sistemi çalışıyor sanıp müdahale gereğini kaçırabilir. Olayı güncel rol/oturum bilgisiyle görünür hale getir. |
| F-02 | P0 | `LobbyService.auto_pick_impl` tamamlanmamış pick action'ını kullanıyor; manuel devir durumu veya kullanıcının manuel tercihini koruyan bir sınır görünmüyor. | Kullanıcı seçim yaptıktan sonra farklı tercih kilitleme riski. Manuel devri aynı action/oturum boyunca koru; yalnız bildirimi kapatmak kontrolü geri almasın. |
| F-03 | P1 | Frontend `role_summoner_spells` değerini rolün ilk şampiyonundan üretiyor; runner başka şampiyonda özel büyü bulamazsa bu kaydı kullanıyor. | Yedek/manuel şampiyon ilk tercihin büyülerini alabilir. İlk tercih büyüsü ile açık rol varsayılanını ayır; son şampiyona göre uygula. |
| F-04 | P2 | `automationIssues` beş rolün tümünde şampiyon ve ban gerektiriyor. | Mid/ADC hazırlayan kullanıcı neden başlayamadığını ancak şartlar bölümünü açınca anlayabilir. Bu davranış korunacaksa autofill gerekçesini açıkla; otomatik olarak gevşetme. |
| F-05 | P1 | Mevcut ortak hata bölümü uzun editörlerin altında yer alıyor. | Acil manuel seçim uyarısı sayfanın altında fark edilmeyebilir. Her görünümde üstte/sabit ve erişilebilir bir uyarı alanı kullan. |

F-02 riskinin gerçek sonucu LCU action durumuna bağlıdır; ayrı sahte oturum testi gerekir.
Rünlerin role göre farklı preset seçimi önceki konuşmada önerildi, ancak mevcut
champion-shared preset seçimini rol bazlı çalışıyor kabul etme.

## Rapor ve tekrar doğrulama

Her bulgu için: kimlik/önem, koşullar, adımlar, beklenen/gerçekleşen, test kanıtı,
öneri ve durum yazılır. Kaynak incelemesi, otomatik tarayıcı testi, görsel inceleme
ve gerçek maç doğrulaması ayrı tutulur.

Mevcut örnek kontroller `frontend/e2e/champions.spec.ts`, `runes.spec.ts` ve
`skins.spec.ts` içindedir. Yeni uyarı akışının testleri eklendiğinde ilgili test
adlarını bu senaryolarla eşleştir. Gerçek oyun komutu içeren bir test doğrudan
canlı backend'e geçirilemez. Henüz çalıştırılmamış senaryolar **test edilmedi** olarak kalır.

### İlk bağımsız kontrol sonucu — 29 Ekim

Çalıştırılan komut:

```powershell
npm run test:e2e -- e2e/champions.spec.ts --grep "saves picks, bans and spells"
```

- 1440, 1024 ve 390 px projelerinde **3/3 geçti**: seçim/büyü kaydı, rol
  geçişi, tercih sırası, ban ve yeniden açma davranışı; yatay taşma kontrolü.
- Masaüstü ve 390 px ekran görüntüleri görsel olarak incelendi. Kontroller
  görünür, mobilde seçim paneli katalogdan önce ve sayfa yatay taşmıyor.
  Görseller sahte PNG olduğundan gerçek portre kalitesi değerlendirilmedi.
- Başlangıç akışındaki "Başlatmak için 7 seçim kaldı" özeti açıklama listesine
  açılıyor; beş rol gerekliliğini kullanıcıya anlatma önerisi F-04 olarak sürüyor.
- UX-01/04/05/07/08/09/10 yeni manuel devir akışı için henüz doğrulanmadı.
  Testler eklendikten sonra yeniden inceleme gerekir. Gerçek profil, hesap ve
  maç kuyruğuna bu kontrolde dokunulmadı.

### Bildirim ilk uygulaması — bağımsız ikinci inceleme

- 1440 ve 390 px'de, Şampiyonlar/Rünler/Kostümler sayfası açıldıktan sonra
  gelen `no_preference` olayı ayrı headless Playwright oturumunda sınandı:
  **6/6 görünüm/genişlik birleşimi geçti**. Uyarı ve Durdur eylemi viewport içinde,
  ses engeli mesajı görünür, yatay taşma yok. Bütün HTTP yazmaları yakalandı;
  gerçekleşen yazma sayısı **0**. Gerçek profil ve oyun durumu kullanılmadı.
- Kaynakta `isInProgress=false` ve manuel hover/kilitli seçim korumaları,
  game/action bazlı kalıcı devir, şampiyona göre büyü fallback sınırı eklendi.
  Backend kabul testleriyle eşleşmeleri `tests/application/test_automation_runner.py`
  içinde görüldü; bu bölümde bu testler agent tarafından ayrıca çalıştırılmadı.
- İlk sabit panelin mobilde gezinme sekmelerini örtmesi F-05'in yeni bir biçimiydi.
  Klavye focus/Enter ile geçiş, dokunma/fare kullanılabilirliğini kanıtlamaz.
  Geliştiriciye normal akışta yer tutan sticky panel ve gerçek `.click()` testi
  önerildi; yerleşim kaynakta buna göre değişti. Tam gezinme yeniden doğrulaması bekliyor.
- Ses beklerken Sesi kapat/Durdur yapılırsa geciken sesin çalması ve eski sonucun
  yeni bildirime yazılması riski bildirildi. Güncel kaynakta bildirim/mute/stop
  guard'ı ve ses iptali eklendi; gecikmeli ses senaryosu ayrıca otomatik test bekliyor.
- "Kayıtlı rün/büyü/kostüm uygulanır" ifadesi, olmayan ayarlar için fazla kesin
  bulundu; metin **"Bu şampiyon için kayıtlı ayarların varsa uygulanır"** olarak
  düzeltildi.
- Beş rolün hepsini zorunlu tutmak, yalnız Mid/ADC hazırlayıp autofill'de manuel
  devretme hedefini engeller. Seçilen ana/ikincil rollerde mevcut gereksinimleri
  koruyup diğer roller için engelleyici olmayan uyarı önerildi. Bu yolun uçtan
  uca doğrulaması validator değişikliği tamamlandıktan sonra yapılacak.

### Son bağımsız kabul turu — Mid/ADC → boş Jungle

Yeni koddan sonra 1440 ve 390 px'de ayrı sahte backend oturumlarıyla şu sıra
gerçek tıklamalarla tamamlandı; iki genişlikte de bütün kontroller geçti:

1. Yalnız Mid ve ADC havuzları/banları tanımlandı. Başlat etkin; eksik autofill
   rolleri için bilgilendirme görünür. Başlat payload'ında Jungle havuzu yok.
2. Mock Start sonrasında Jungle `no_preference` olayı geldi. Atanan rol ve League'de
   yapılacak manuel işlem açık; ses bulunmadığında görsel yedek mevcut.
3. Bildirim açıkken Rünler ve Kostümler'e fare/dokunma karşılığı `.click()` ile
   geçildi. Bildirim viewport içinde kaldı; mobil sekmeler artık örtülmüyor.
4. Mock League manuel kilit sonucu bildirimi temizledi. Sonra yeni `all_unavailable`
   olayı gösterildi; bildirimin Durdur düğmesi mock Stop'u bir kez gönderip durumu temizledi.
5. Her genişlikte **1 mock Start, 1 mock Stop, 0 profil yazması ve 0 tarayıcı hatası**.
   Gerçek Riot/League hesabı, maç kuyruğu veya profil kullanılmadı.

Masaüstü ve mobil viewport görüntüleri görsel olarak da incelendi: sticky panel
normal akışta yer tutuyor; başlık/manuel seçim metni, ses engeli açıklaması ve
üç eylem okunur. Bu test kapsamı içinde açık önemli kullanılabilirlik engeli kalmadı.

Kanıt: agent'in bağımsız headless Playwright koşumu ve geçici
`frontend/test-results/ux-agent-final-1440.png`, `ux-agent-final-390.png` görüntüleri.
Bu klasör sonraki Playwright koşumunda temizlenebilir; kalıcı sonuç bu belgededir.

Sınırlar: gerçek maçta rol atama/ban/manuel kilit denenmedi. Sesin gerçekten
duyulması ve engel kalktıktan sonraki cihaz davranışı fiziksel ortamda doğrulanmadı.
Gecikmeli ses iptali, sağlık bağlantısı kesilmesi ve backend'in yanlış büyü
uygulamaması için ürün testleri/kaynakları incelendi; bu son tur bunları ayrı bir
gerçek LCU oturumunda sınamadı. Rünlerin rol bazlı preset ayrımı ayrıca geliştirilmedikçe
mevcut şampiyon bazlı ortak seçim geçerlidir.

## Hesaplar ekranı — kabul senaryoları

> **10 Kasım 2026 kapsam değişikliği:** Hesaplar, parola saklama ve otomatik
> Riot girişi kullanıcı isteğiyle kaldırılmaktadır. Aşağıdaki Hesaplar kabulü ve
> geçmiş test sonuçları tarihsel kayıttır; artık ürünün beklenen davranışını
> tanımlamaz. Güncel hedef ve doğrulama belgenin sonundaki kaldırma bölümündedir.

Bu bölüm React Hesaplar ekranı geliştirilmeden önce hazırlanmıştır. Kaynaklar:
`account_endpoints.py`, `account_model.py`, `account_service.py`,
`login_job_service.py` ve eski Qt hesap denetleyicisi. **Yeni ekranın testleri
henüz çalıştırılmadı.** Yalnız anonim fixture kullanılır; gerçek hesap listesi bile
okunmaz. Gerçek hesap/profil kaydı, login, League launch veya maç kuyruğu hiçbir
senaryoda çalıştırılmaz. Bütün HTTP istekleri test backend'inde tutulur.

### Kullanıcı hedefleri ve kabul ölçütleri

| Kimlik | Öncelik | Başlangıç ve eylem | Beklenen kullanıcı sonucu |
| --- | --- | --- | --- |
| A-01 | P1 | Hesap listesi gecikir; sonra boş liste döner. Ayrı koşumda GET 503 döner. | Yükleme, gerçekten boş liste ve hata ayrıdır. Hata "kayıtlı hesap yok" diye gösterilmez. Yeniden deneme vardır; hatada mevcut metadata silinmez. |
| A-02 | P1 | Anonim kullanıcı ilk hesabı ekler; gerekli alanları boş/boşlukla gönderir. | Riot giriş kullanıcı adı ile oyun adı/etiket ayrımı anlaşılır. Oluşturmada kullanıcı adı ve parola gerekir; başarıdan önce kart eklenmez. Kayıt başarılıysa tek kart görünür. |
| A-03 | P0 | Var olan hesabın adını düzenler; parola boş bırakılır veya gönderilmez. | Eski parola korunur; kullanıcıya boş bırakmanın anlamı açıkça söylenir. Eski düz/şifreli parola forma doldurulmaz. Yeni parola girilirse karakterler aynen korunur; parola `.trim()` edilmez. |
| A-04 | P1 | Formu iptal etme, başarılı gönderme, hata ve sayfa değiştirme. | Parola gereksiz biçimde bellekte/DOM'da kalmaz; form kapandığında temizlenir. Hata durumunda hassas olmayan alanlar kaybolmaz. HTTP hata gövdesi/console/storage parolayı içermez. |
| A-05 | P1 | Hesabı kaldırma eylemi; önce vazgeç, sonra onayla. | Hangi anonim hesabın kaldırılacağı açık, işlem RunePilot kaydına aittir; Riot hesabı siliniyormuş gibi anlaşılmaz. Vazgeç/Escape HTTP DELETE göndermez. Onay tek hedefe tek DELETE gönderir; varsayılan odak iptaldedir. |
| A-06 | P1 | Create/update/delete yanıtı kaybolur veya HTTP 500 döner. | Başarılı gibi gösterilmez. Özellikle idempotent olmayan create POST körlemesine tekrarlanıp çift kayıt oluşturmaz; önce liste ve sonuç doğrulanır. Diğer hesaplar ve oyun ayarları korunur. |
| A-07 | P0 | Otomasyon çalışıyor veya sağlık durumu bilinmiyor; kullanıcı giriş yapmak ister. | Hesap geçişi doğrudan başlamaz. Durdurma gerekiyorsa kullanıcıya açık eylem sunulur; Stop ve sağlık doğrulaması tamamlanmadan login/launch POST gönderilmez. |
| A-08 | P0 | Kaydı bekleyen oyun ayarı, başarısız kayıt, çakışma veya kaydedilmemiş rün taslağı varken giriş istenir. | Başarısız kaydı atlayıp hesap değişmez. Rün taslağı için kaydet/geri al yolu anlaşılır; işlem iptal edilirse taslaklar korunur. Yeni login başlangıcı son ayar kaydını ve gerekli Stop'u bekler. |
| A-09 | P0 | Login POST sunucuda kabul edilir ama yanıtı kaybolur. | Aynı `request_id` korunur; bilinen UUID ile iş sorgulanır/gerekirse aynı POST tekrarlanır. Yeni UUID veya tekrar parola gönderimiyle ikinci giriş başlatılmaz. Kullanıcıya sonucun henüz doğrulanamadığı söylenir. |
| A-10 | P1 | Giriş düğmesine hızlı çift tıklanır veya başka hesap seçilip giriş istenir; backend 409 dönebilir. | Tek aktif iş vardır. Tekrarlı istek engellenir; çalışan işin hesabı/durumu korunur. Çakışma genel "parola yanlış" hatası gibi gösterilmez. |
| A-11 | P1 | Giriş sürerken Şampiyonlar/Rünler/Kostümler ekranına gidilir, geri dönülür. | İş state'i görünüm dışında yaşamaya devam eder; yeniden POST yoktur. Görünüm değiştirmek işi iptal etmiş gibi sunulmaz. Devam eden giriş fark edilir ve aynı hesaba bağlı kalır. |
| A-12 | P1 | Job sorgusu geçici ağ hatası/503 verir; sonra düzelir. Ayrı durumda job 404 veya farklı account_id/id döner. | Geçici hatada aynı iş izlenir. 404 veya eşleşmeyen işte başarı varsayılmaz, yeni giriş otomatik başlatılmaz; Riot Client'ı kontrol etme yolu gösterilir. |
| A-13 | P1 | Yanlış parola veya sınıflandırılmış giriş hatası döner. | Kullanıcı metadata'yı düzenleyip yeniden deneyebilir. Eski iş bitmeden yeni iş açılmaz; hata otomatik tekrar döngüsüne girmez. Hassas ham Riot yanıtı gösterilmez. |
| A-14 | P1 | CAPTCHA/2FA veya bekleyen doğrulama vardır. | Kullanıcı Riot Client'a yönlendirilir; uygulama kod/CAPTCHA çözmesini kendi içinde istemez. İş gerçekten sürerken kullanıcıya bitmiş gibi gösterilmez. Doğrulama sonrası devam, kimlik bilgilerini tekrar göndermekten ayrıdır. |
| A-15 | P1 | Login sonucu `terms_required` veya League launch sonucu `requires_terms=true`. | Girişin tamamlandığı fakat anlaşmanın kullanıcı tarafından incelenmesi gerektiği açıklanır. Kullanıcı Riot Client'ta kendisi kabul eder; otomatik kabul/tekrar login yapılmaz. |
| A-16 | P1 | `launch_failed`; kullanıcı League'i başlatıp devam etmeyi dener, yanıt gecikir/kaybolur. | Login baştan yapılmaz; yalnız ayrı launch devam yolu kullanılır. Çift tıklama ikinci launch başlatmaz. Başarısızlıkta ekran ve hesap metadata'sı korunur; yeni deneme kullanıcı eylemidir. |
| A-17 | P1 | Hesap listesi yüklenmiyor veya kullanıcı giriş yapmadan devam eder. | Girişsiz devam yeni login/launch/queue POST üretmez. Aktif/belirsiz login veya launch sırasında başka işlem başlatacak bir kaçış yolu olmaz. Offline ekranda League gerektiren işlerin kullanılabilirliği doğru gösterilir. |
| A-18 | P0 | Başarılı hesap geçişi sonrası aynı şampiyonun kostüm ekranı yeniden açılır. | Eski hesabın sahip olunan şampiyon/kostüm verisi kullanılmaz. Devam eden eski yanıtlar yok sayılır. Yeni hesapta olmayan kayıtlı kostüm kimliği silinmez; kullanılamama uyarısı gösterilir. |
| A-19 | P1 | CRUD güncellenirken liste yenilenir, seçili hesap kaldırılır veya başka form açılır. | Geç yanıt yeni hedef hesabın formunu ezmez. Silme onayı liste sırasına değil yakalanan hesap kimliğine bağlıdır. İş sürerken çelişen düzenlemeler engellenir. |
| A-20 | P1 | 390 px ve klavyeyle ekle/düzenle/onayla/iptal/giriş durumu gezinmesi. | Etiketler görünür ve input'a bağlı; parola input'u maskeli; odak görünür. Uzun anonim isimler taşmaz; butonlar kesilmez. Dialog varsa Escape ve odak geri dönüşü çalışır; kritik eylem yalnız hover ile bulunmaz. |
| A-21 | P0 | Anonim sentetik parola ile tüm başarılı/hatalı kayıt yolları. | Düz veya şifreli parola hesap listesinin yanıtına, URL'ye, loga, console'a, localStorage/sessionStorage'a ya da rapor/screenshot'a düşmez. Login çağrısı yalnız account_id/request_id taşır. |

### İlk kaynak incelemesi — React uygulaması öncesi

Bu maddeler yeni React ekranında yeniden üretilmiş hata değildir; mevcut
sözleşmelerin yeni arayüzde korunması gereken sınırları ve somut riskleridir.

| Kimlik | Önem | Kaynakta doğrulanan sınır | React için gerekli davranış |
| --- | --- | --- | --- |
| A-F01 | P0 | `LoginJobService` UUID `request_id` değerini iş kimliği olarak kullanır; aynı UUID/hesap aynı işi döndürür, farklı aktif iş 409 olur. | Belirsiz POST sonucunda UUID'yi değiştirme. Page navigation sırasında controller/job state'i unmount etme; yanlış account_id/id yanıtını kabul etme. |
| A-F02 | P1 | Hesap oluşturma POST'u için login benzeri idempotency anahtarı yoktur. | Yanıt kaybını otomatik create tekrarıyla çözme; kaydın sonucunu listeyi yeniden okuyarak doğrula. Aynı isimli kaydı ayırt edemiyorsan başarı iddia etme. |
| A-F03 | P0 | Account/login API, frontend'in kaydedilmemiş rün formunu ve çalışan otomasyon state'ini bilmez. | Giriş ve launch öncesi açık workspace kapısı gerekir: ayar kaydı/çakışma, rün taslağı, Stop ve sağlık doğrulaması. Sadece disabled düğme yeterli değil; handler da aynı koşulları kontrol etmeli. |
| A-F04 | P1 | `SkinGallery` hesap sahipliğini `api/championId/yerel attempt` değişince yeniler; aynı şampiyonda hesap değişimi tek başına bu bağımlılıkları değiştirmez. | Başarılı login sonrasında hesap bağımlı kaynakları epoch/invalidation ile yenile; eski hesabın skin listesini kullanma. Yeni hesapta olmayan eski seçimi silme. |
| A-F05 | P1 | Login başarısından sonra `launch_failed` ve `terms_required` ayrı sonuçlardır. Manuel doğrulama backend job'u bir süre running tutabilir. | "Giriş başarısız" diyerek parola akışını baştan başlatma; durum ve sonraki kullanıcı eylemini ayrı göster. Running iş için sahte yüzde veya kesin bitiş süresi verme. |
| A-F06 | P0 | GET hesap yanıtı yalnız metadata içerir. Update'te yalnız tam boş parola eskiyi korur; yeni parola backend'de şifrelenir. | Parolayı metadata/state genel kaydına katma, boş parolayı yeni hesapta kabul etme, girilmiş yeni parolayı kırpma. |
| A-F07 | P1 | İş geçmişi süreç içidir ve sınırlıdır; uygulama yenilenince kaybolan iş bilgisi için aktif iş listesi endpoint'i yoktur. | Kaybolan/404 işi otomatik yeni login ile telafi etme. Belirsiz işlemi kullanıcıya bildir; sayfa gezintisi ile tam yeniden yükleme sınırlarını ayır. |

Silme onayının örnek metni: **"Bu hesabı RunePilot'tan kaldırmak istiyor musun?
Riot hesabın silinmez."** Örnek hesap adları bütünüyle sentetik olmalıdır.

### Doğrulama durumu

- Bu aşamada yalnız kaynak ve mevcut anonim backend testleri okundu. Yeni
  Hesaplar ekranı için tarayıcı testi veya gerçek işlem çalıştırılmadı.
- İlk bağımsız tarayıcı turu, hazır UI üzerinde bütün HTTP yollarını yakalayan
  sahte backend ile yapılacak. Beklenmeyen write/login/launch isteği gerçek
  servise geçirilmeyecek; test hata vererek duracak.
- Kayıp POST, eski job yanıtı, 409 ve backend yeniden başlama senaryoları fixture'da
  ayrı ayrı üretilecek. Sadece mutlu yolun geçmesi kabul için yeterli değildir.
- Gerçek hesap/oturum/profil veya gerçek League başlatma bu UX görevinde kapsam dışıdır.

### Son bağımsız Hesaplar doğrulaması — React ekranı hazır

Yeni ekran ve controller kaynakları incelendi. Yukarıdaki ilk inceleme tarihsel
başlangıç durumudur: aktif işi yeniden bulmak için artık `GET /login-jobs/active`
vardır; kökte yaşayan controller sayfa geçişlerinde iş takibini korur. Hesap
geçişi oyun ayarlarının kaydını ve Stop'u bekler; hesap değişiminde kaynak epoch'u
yenilenir. Belirsiz CRUD yanıtından sonra liste doğrulanmadan yeni yazma açılmaz.

Bağımsız koşum:

```text
npm.cmd run test:e2e -- e2e/accounts.spec.ts --project desktop --project mobile-width --output test-results-ux-accounts-final
12 passed (20.8s)
```

Altı senaryo hem masaüstünde hem 390 px genişlikte geçti:

- Boş listeden hesap ekleme, boş parola ile düzenleme ve onaylı kaldırma.
  Sentetik yeni parolanın baş/son boşlukları aynen gönderildi; boş edit parolası
  isteğe eklenmedi. Vazgeç DELETE üretmedi; oyun ayarları korundu.
- Kaybolan create yanıtında otomatik POST tekrarı engellendi. Parola alanı
  temizlendi; liste yenilemesi oluşmuş kaydı gösterdi; tek create gönderildi.
- Mock otomasyon Stop'u login'den önce gerçekleşti. Kaybolan login POST'u aynı
  iş kimliğiyle izlendi; sayfalar arasında durum görünür kaldı ve ikinci login
  gönderilmedi. Yeni hesapta bulunmayan kayıtlı kostüm korunup uyarıldı.
- Sayfa açılışında aktif iş yeniden bulundu. Koşulları kullanıcıya bırakan durum
  ve iki açık launch denemesi, yeni login/parola gönderimi olmadan ilerledi.
- Liste hatasında girişsiz gezinme mümkün kaldı. Kaydedilmemiş rün taslağı login'i
  engelledi; bu senaryoda hiçbir login/launch/Stop isteği oluşmadı.
- Yüklenemeyen oyun ayarlarının giriş düğmelerini neden engellediği açıklandı;
  yeniden yükleme ile düzeldi. Yeni hesap formunun ilk alanı odak aldı; iptal
  sonrası odak formu açan düğmeye döndü. Kurtarma login veya launch başlatmadı.

İlk bağımsız koşum da 10/10 geçmişti. O incelemede kaynak üzerinden bildirilen
iki P2 önerisi — ayar yükleme hatasının Hesaplar'da açıklanması ve form odağı —
üründe giderildi; son iki genişlikte yeni kabul testiyle doğrulandı. Parola
açıklaması kullanıcı dilinde "bu cihazda" olarak sadeleştirildi.

Masaüstü ve 390 px anonim ekran görüntüleri görsel olarak incelendi. Hesap kartı,
giriş, League devam ve girişsiz devam eylemleri okunur; yatay taşma yok. Sentetik
parola body metninde veya localStorage/sessionStorage'da bulunmadı; yakalanan
tarayıcı hatası yok. İncelenen kapsamda açık P0/P1 UX engeli kalmadı.

Kanıt: `frontend/test-results-ux-accounts-final` ayrı Playwright çıktı dizini;
görsel inceleme ilk koşumun `frontend/test-results-ux-accounts` dizinindeki
`accounts-workspace.png` dosyaları üzerinde yapıldı. Çıktılar geçicidir; kalıcı
sonuç bu belgededir. Tüm API yolları anonim fixture tarafından yakalandı;
gerçek hesap listesi, profil, Riot oturumu, League launch veya kuyruk kullanılmadı.

Sınırlar: gerçek CAPTCHA/2FA/EULA, gerçek parola şifreleme/cihaz logları, fiziksel
mobil klavye ve uzun hesap listesiyle kaydırma bu turda denenmedi. 409, kayıp/beklenmeyen
job kimliği, geciken eski yanıt ve launch ağ hatalarının tamamı bağımsız tarayıcı
koşumunda ayrı ayrı üretilmedi; ilgili controller korumaları kaynakta incelendi.
Kabul tablosundaki her satırın bütünüyle çalıştırıldığı sonucu çıkarılmamalıdır.

## Hesaplar özelliğinin tamamen kaldırılması — 10 Kasım 2026

Kullanıcı Riot Client ve League'i kendisi açar, giriş/doğrulama/koşullar işlemlerini
Riot arayüzünde tamamlar. RunePilot oyun seçimlerini düzenlemek ve açık League
istemcisi üzerinden otomasyon için kullanılır. Hesap listesi veya giriş aracısı
olarak davranmaz. Aşağıdaki kontroller gerçek hesap/profil yerine yalnız anonim
mock API ve geçici dosya fixture'larıyla yürütülür.

### Kaldırma kabul senaryoları

| Kimlik | Öncelik | Koşul ve eylem | Beklenen sonuç |
| --- | --- | --- | --- |
| R-01 | P1 | Qt uygulaması `run_app.py` ve doğrudan presentation main yolu üzerinden açılır. | Ana seçim penceresi doğrudan görünür; LoginWindow, hesap seçimi ve girişsiz devam basamağı yoktur. Başlangıç Riot/League süreci açmaz ve giriş isteği göndermez. |
| R-02 | P1 | React masaüstü/390 px menüsü, yardım ve bütün sayfaları gezilir. | Yalnız Şampiyonlar/Rünler/Kostümler erişimi vardır. Hesaplar bağlantısı, parola alanı, giriş durumu şeridi, CAPTCHA/EULA/launch eylemi ve hesap yükleme bekleyişi yoktur. |
| R-03 | P1 | Backend erişilebilir, League kapalıdır; sonra mock League verisi geri gelir ve yenilenir. | Servis bağlantısı ile League hazırlığı karıştırılmaz. Kullanıcı League'i kendisi açıp giriş yapmaya yönlendirilir; Yenile ile kurtulur. Otomasyon kendiliğinden başlamaz, kaydedilmiş seçimler silinmez. |
| R-04 | P0 | Eski `/accounts`, `/accounts/{id}`, `/accounts/{id}/login`, `/login-jobs/active`, `/login-jobs/{id}` ve `/league/launch` yolları eski HTTP metotlarıyla çağrılır. | Kayıt okuma/yazma veya Riot işlemi gerçekleşmez; kaldırılan API yolları erişilebilir değildir. Vite proxy bu yolları yeniden açmaz. Doğrudan API ve proxy cevapları ayrı doğrulanır. |
| R-05 | P0 | Backend composition, health ve otomasyon normal fixture ile çalışır. | AccountService/LoginJobService/LeagueLaunchService kurulmaz. Health'te giriş işi bekleyişi kalmaz; normal Start/Stop/kayıt akışı eski hesap state'ine bağımlı değildir. |
| R-06 | P0 | Geçici mevcut ve legacy config'lerde anonim `accounts` kayıtları, oyun ayarları ve ilgisiz anahtarlar bulunur. | Belgelenen migration bu hesap kayıtlarını temizler; rün/kostüm/şampiyon/rol/büyü ayarları ve diğer ilgisiz anahtarlar korunur. Legacy fallback bir sonraki açılışta eski hesabı geri taşımaz. |
| R-07 | P0 | Aynı geçici fixture'da başarısız migration yazması, bozuk JSON ve `.tmp` kalıntısı üretilir. | Hata gizlenmez; bozuk profili boş varsayıp oyun ayarlarıyla üzerine yazma yapılmaz. Kayıtlar loga/yanıta dökülmez. Temizlik başarılı olmadan başarılı temizlendi iddiası yapılmaz. `.tmp` politikası yalnız bilinen dosyalara uygulanır. |
| R-08 | P1 | Kaynak, bağımlılıklar, build girdileri ve yardımcı scriptler taranır. | Parola şifreleme/deşifre ve Riot login/launch yolları, yardımcı `test_login.py`, artık kullanılmayan bağımlılık ve paket girdileri kalmaz. League oyun otomasyonu için gerekli yerel LCU bağlantısı korunur. |
| R-09 | P1 | League'de kullanıcı manuel hesap değiştirir; RunePilot'ta Listeyi yenile ve kostüm yenileme uygulanır. | Yeni sahiplik okunur; eski hesapta bulunan kostüm yeni hesapta kullanılabilir varsayılmaz. Kullanılamayan kayıtlı seçim kimliği silinmez, anlaşılır uyarı verilir. Eski account epoch kaldırılırken yenileme yolu kaybolmaz. |
| R-10 | P0 | Mevcut ayar düzenleme/kaydetme, rün taslağı, manuel şampiyon devri ve Stop senaryoları çalışır. | Hesap kodu temizliği ayar kaybına, otomatik Start'a veya kullanıcının şampiyon seçiminin ezilmesine yol açmaz. Normal üç sayfada uyarı görünürlüğü korunur. |
| R-11 | P1 | Yeni ekran başlangıcında ve sayfa gezintilerinde HTTP istekleri yakalanır. | Hesap/login/launch isteği sayısı sıfırdır. DOM/storage içinde kimlik bilgisi formu veya yeni kayıt yoktur. Uygulamanın yerel API oturum belirteci, Riot parolasıyla karıştırılıp kaldırılmaz. |
| R-12 | P2 | 390 px ve klavyeyle üç sayfa arasında geçilir; League kapalı bildirimi okunur. | Üç sekme eşit ve okunur; eski dördüncü menü boşluğu kalmaz. Bildirim gezinme/Start/Stop düğmelerini örtmez; sonraki eylem açıktır. |

### İlk salt okunur kapsam incelemesi

- `run_app.py` başlangıcı Riot açma çağrısı, Qt `main()` ise LoginWindow içeriyordu;
  React sayfasını kaldırmak tek başına bu giriş yollarını kapatmaz.
- `ConfigRepository` mevcut `%APPDATA%/RunePilot/user_config.json` ile legacy
  `%APPDATA%/LoLAutomation/user_config.json` fallback'ini tanır. Yalnız mevcut
  dosyanın `accounts` alanını kaldırmak legacy kalıntısını temizlemez. Bu yollar
  yalnız kaynak sabitlerinden öğrenildi; gerçek kullanıcı dosyaları okunmadı.
- `crypto.py` bağımsız bir kimlik/anahtar dosyası oluşturmuyor; türetilmiş Fernet
  anahtarı kullanıyor. Kanıt olmadan başka dosya silme listesi çıkarılmamalı.
  LCU lockfile'daki geçici yerel bağlantı bilgisi League otomasyonunun ayrı ihtiyacıdır.
- `test_login.py`, bağımlılıklar ve Vite proxy izinleri UI'dan ayrı kaldırma
  yüzeyleridir. Güvenlik nedeniyle tam kaldırma iddiası bu kaynakları da kapsamalı.

### Kaldırma sonrası bağımsız son inceleme

**Sonuç:** incelenen kaynak kapsamında tamamlamayı engelleyen P0/P1 kaldırma
sorunu saptanmadı. Bu sonuç bağımsız tarayıcı veya gerçek istemci doğrulaması değildir.

- `run_app.py` artık Riot açma çağrısı yapmıyor. Qt `main()` doğrudan `MainWindow`
  oluşturup gösteriyor; giriş penceresi araya girmiyor.
- React `App` yalnız Şampiyonlar, Rünler ve Kostümler görünümünü barındırıyor.
  Hesap menüsü/controller'ı, giriş işi şeridi ve parola formu kaldırılmış.
  Yardım metni kullanıcıya Riot'ta kendisi giriş yapıp League'i açmasını söylüyor.
- Composition artık hesap/giriş/launch servislerini kurmuyor. Repository başlangıç
  temizliği mevcut ve legacy bilinen profilleri ve `.tmp` dosyalarını kapsıyor;
  başarısız veya bozuk veri temizliği startup'ı hata ile durduruyor. Genel okuma
  ve yazma yolları `accounts` alanını dışlıyor; eski kayıtların yeniden taşınma
  riski için kaynak koruması var.
- Rünleri yenile ve Kostümleri yenile eylemleri korunmuş. Kullanıcı Riot'ta elle
  hesap değiştirdiğinde kostüm yenilemesi yeni sahipliği sorgular; kayıtlı ama
  artık bulunmayan kostüm kimliği silinmeden uyarılır. Bu turda bu yol tarayıcıda
  yeniden üretilmedi; kaynak incelemesiyle doğrulandı.

**Root tarafından bildirilen doğrulama:** 245 Python ve 54 frontend testi, build
ve tam E2E koşumunda 73 geçen/8 atlanan test. Root eski API yollarının backend ve
Vite proxy üzerinden 404 döndüğünü; gerçek mevcut/legacy iki profilde `accounts`
alanının temizlendiğini ve hesaplar dışındaki JSON içerik hash'lerinin korunduğunu
doğruladı. Yardımcı gerçek giriş scripti ve geliştirici `/test-login` komutu da
kaldırıldı. Bunlar bağımsız UX agent'inin çalıştırdığı test veya profil incelemesi
olarak değerlendirilmemelidir.

**Bağımsız tarayıcı sınırı:** bütün API isteklerini anonim fixture ile yakalayan
masaüstü/390 px koşumu için hazırlanan izin bekleyen bağımsız tarayıcı komutu root
tarafından sonlandırıldı; bağımsız tur yapılmadı. `test-results-ux-removal` kanıtı veya yeni ekran
görüntüsü üretilmedi. Eski Hesaplar ekranının geçmiş 12/12 sonucu kaldırma kabulü
için kanıt değildir. R-02/R-03/R-09/R-12'nin kaldırma sonrası görsel/etkileşimli
bağımsız doğrulaması yapılmamış olarak kalır; root E2E kapsamı ayrı kanıttır.

Bu görevde UX agent'i gerçek profil veya credentials okumadı/değiştirmedi;
Riot/League oturumu, gerçek login, launch veya kuyruk çalıştırmadı. Değişiklik
kapsamı yalnız bu QA raporudur.
