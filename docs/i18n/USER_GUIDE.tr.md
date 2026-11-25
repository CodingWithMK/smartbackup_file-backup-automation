<!-- Source: docs/USER_GUIDE.md | Version: 0.9.0 | Language: tr (Türkçe) | Synced: 2026-11-25 -->

# SmartBackup Kullanıcı Kılavuzu

**Test edilen sürüm: `smartbackup 0.9.0`** · Platformlar: Windows · macOS · Linux · Python 3.9+

🌐 [English](../USER_GUIDE.md) · **Türkçe** · [Deutsch](USER_GUIDE.de.md)

Bu kılavuz, SmartBackup'ı kullanmak için tek doğruluk kaynağıdır. Burada belgelenen her komut,
seçenek, varsayılan değer, dosya yolu ve davranış doğrudan proje kaynak kodundan alınmış ve
doğrulanmıştır.

---

## İçindekiler

1. [Genel Bakış ve Felsefe](#1-genel-bakış-ve-felsefe)
2. [Kurulum ve Ön Koşullar](#2-kurulum-ve-ön-koşullar)
3. [Temel Kavramlar](#3-temel-kavramlar)
4. [CLI Komut Başvurusu ve Günlük Tarifler](#4-cli-komut-başvurusu-ve-günlük-tarifler)
5. [Otomatik Algılama Servisi ve İzleyici Kılavuzu](#5-otomatik-algılama-servisi-ve-izleyici-kılavuzu)
6. [Veri Kurtarma ve Geri Yükleme Kılavuzu](#6-veri-kurtarma-ve-geri-yükleme-kılavuzu)
7. [Yapılandırma ve Özel Hariç Tutma Kuralları](#7-yapılandırma-ve-özel-hariç-tutma-kuralları)
8. [Platform Ayrıntıları ve Sorun Giderme](#8-platform-ayrıntıları-ve-sorun-giderme)
9. [Ekler](#9-ekler)

---

## 1. Genel Bakış ve Felsefe

**SmartBackup**, geliştiricilerin çalışma verilerini (varsayılan olarak `Documents` klasörünüzü)
harici bir sürücüye yedeklerken `node_modules`, sanal ortamlar, derleme çıktıları, sürüm
kontrol meta verileri ve önbellekler gibi geliştirme artıklarını otomatik olarak atlar.

### Temel özellikler

| Özellik | Pratikte ne anlama gelir? |
|---|---|
| **Akıllı filtreleme** | Dört katmanlı hariç tutma motoru (tam adlar, dosya uzantıları, glob kalıpları, sanal ortam yapı algılama), yeniden oluşturulabilen gigabaytlarca çıktıyı hiç kopyalamadan atlar. |
| **Minimal bağımlılık** | Çalışma zamanı yalnızca [`rich`](https://github.com/Textualize/rich) ve [`typer`](https://github.com/tiangolo/typer) gerektirir. Sıkıştırma, özetleme (hashing), manifest yönetimi ve geri yükleme tamamen Python standart kütüphanesiyle çalışır — harici ikili dosya gerekmez. |
| **Manifest tabanlı değişiklik algılama** | *Yedekleme diskinde* saklanan JSON (`.smartbackup_manifest.json`) veya SQLite (`.smartbackup_manifest.db`) manifesti her dosyanın boyutunu, değişiklik zamanını (`mtime`) ve isteğe bağlı SHA-256 özetini tutar; sonraki çalıştırmalar yalnızca yeni/değişen dosyaları kopyalar ve kaynaktan sildiğiniz dosyaları yedekten kaldırır. |
| **Makine adına göre cihaz izolasyonu** | Her bilgisayar `Documents-Backup/<hostname>/` altına yedekleme yapar; böylece birden fazla bilgisayar aynı harici diski birbirinin üzerine yazmadan güvenle paylaşır. |
| **Platformlar arası, sıfır yapılandırma** | Windows, macOS ve Linux üzerinde otomatik `Documents` klasörü bulma, harici sürücü algılama ve yerel terminal/işletim sistemi entegrasyonu kutudan çıktığı gibi çalışır. |

### SmartBackup *ne değildir*?

- **Bir arşivleme/sürümleme sistemi değildir.** Kaynağınızdaki silmeler **yedeğe de yansıtılır**
  (kaynağın birebir aynasını tutar). Değiştirilen dosyaların eski sürümlerini saklamaz.
- **Şifreli değildir.** Şu anda şifreleme desteği yoktur (yol haritasında yer almaktadır).
- **Tekilleştirmeli (deduplicating) veya uzak yedekleme aracı değildir.** SSH, bulut arka uçları,
  blok düzeyinde tekilleştirme veya saklama (retention) politikaları içermez.

SmartBackup'ı hızlı, yerel, "çalışma dosyalarımı USB belleğe kopyala" yedeklemeleri için kullanın.
Zaman noktasına geri dönüşlü (point-in-time) felaket kurtarma için başka bir çözüm kullanın veya
SmartBackup'ı bunun yanında konumlandırın.

### Gereksinimler

- Python **3.9 veya üzeri** (`requires-python = ">=3.9"`) — veya bağımsız çalıştırılabilir ikili dosya kullanıyorsanız Python gerekmez
- Yazılabilir bir hedef: harici disk, USB bellek veya seçtiğiniz herhangi bir dizin
- Hedefte en az ~100 MB boş alan (otomatik algılayıcı tarafından zorunlu kılınan alt sınır)

---

## 2. Kurulum ve Ön Koşullar

Bu kılavuzdaki tüm örnekler `smartbackup` komutunu kullanır. Paketi kurmadan kullanıyorsanız her
örnek depo kökünden `python main.py` veya `python -m smartbackup` ile de birebir çalışır.

### Seçenek 1 — Doğrudan çalıştırma (kurulum gerektirmez)

```bash
git clone https://github.com/CodingWithMK/smartbackup_file-backup-automation.git
cd smartbackup_file-backup-automation

python main.py            # kurulum adımı olmadan doğrudan yedekleme yapar
```

`main.py`, `src/` dizinini otomatik olarak `sys.path`'e ekler; kurulum gerekmez.

### Seçenek 2 — pip ile kurulum

```bash
git clone https://github.com/CodingWithMK/smartbackup_file-backup-automation.git
cd smartbackup_file-backup-automation

pip install .             # standart kurulum → `smartbackup` komutunu sağlar
```

Düzenlenebilir (geliştirme) kurulumu:

```bash
pip install -e ".[dev]"   # -e = canlı düzenlenebilir, [dev] pytest, pytest-cov ve ruff ekler
```

### Seçenek 3 — uv ile kurulum (geliştiriciler için önerilen)

```bash
git clone https://github.com/CodingWithMK/smartbackup_file-backup-automation.git
cd smartbackup_file-backup-automation

uv venv
source .venv/bin/activate          # Windows (PowerShell): .venv\Scripts\Activate.ps1
                                   # Windows (CMD):        .venv\Scripts\activate.bat
uv pip install -e ".[dev]"
```

### Kurulumu doğrulama

```bash
smartbackup --version
# smartbackup 0.9.0

smartbackup --help          # tam seçenek listesi (her alt komut için de geçerlidir)
```

### Kaldırma / güncelleme

```bash
pip uninstall smartbackup
pip install . --upgrade      # güncel bir kopyadan yükseltmek için
```

### Giriş noktaları özeti

| Giriş noktası | Kurulum gerekir mi? | Notlar |
|---|---|---|
| `smartbackup` | Evet (`pip install .` veya bağımsız kurucu) | `smartbackup = smartbackup:main` olarak tanımlı konsol komutu |
| `python -m smartbackup` | Evet (paket içe aktarılabilir olmalı) | Konsol komutu ile aynı kod yolu |
| `python main.py` | Hayır | Depo kökü kolaylık çalıştırıcısı; `src/` yolunu `sys.path`'e ekler |

---

## 3. Temel Kavramlar

### 3.1 Artımlı Manifest Takibi

Her yedekleme çalışmasının ardından SmartBackup, yedekleme diskine bir manifest yazar:

```
<backup>/Documents-Backup/<Device>/.smartbackup_manifest.json
```

*(Veya `--manifest-format sqlite` kullanıldığında `.smartbackup_manifest.db`.)*

Manifest her dosya için şu alanları kaydeder: `hash` (SHA-256, isteğe bağlı), `size`, `mtime`,
`permissions`, `backed_up_at` — ayrıca üst bilgi meta verileri: `source` (orijinal kaynak yolu),
`hostname`, `hash_algorithm`, `backup_count`, `total_files`, `total_size`, `created`, `updated`.

**Bir çalıştırmanın nelerin kopyalanacağına karar verme sırası:**

1. Hariç tutma kurallarını uygulayarak kaynak ağacını tara (bkz. [3.5](#35-neler-hariç-tutulur)).
2. Her kaynak dosyasını manifestteki kaydıyla sırayla karşılaştır:
   - **boyut (`size`)** farklıysa → değişti (`modified`)
   - **değişiklik zamanı (`mtime`)** farklıysa → değişti (`modified`)
   - her iki tarafta da **özet (`hash`)** varsa ve farklıysa → değişti (`modified`)
   - manifestte yoksa → yeni (`new`)
   - manifestte olup kaynakta karşılığı olmayan kayıt → **silindi (`deleted`)** (yedekten kaldırılır)
3. Yeni dosyaları kopyala, değişenleri güncelle, artık kullanılmayanları sil (çok iş parçacıklı,
   en fazla `min(8, CPU sayısı)` işçi).
4. Manifesti atomik olarak yeniden yaz (geçici dosya + yeniden adlandırma; elektrik kesintisinde
   bozulmayı önler).

**Temel sonuçlar:**

- **Silmeler yedeğe de yansıtılır.** Bir dosyayı yerel olarak silmeniz, bir sonraki yedeklemede
  sürücüden de silinmesi anlamına gelir. Bu bilinçli bir tasarımdır — SmartBackup çalışma kümenizin
  aynasını tutar.
- **Manifest hedef diskte yaşar**; böylece SmartBackup'ı yeniden kursanız bile artımlı durum
  kaybolmaz.
- **`--no-manifest`**, manifest takibini kapatır ve geleneksel kaynak-yedek karşılaştırmasına
  (`ChangeDetector`: boyut + mtime, `--hash` açıksa ayrıca özet) geri döner.
- **Bozuk/eksik manifest** ölümcül değildir: bir uyarı yazdırılır ve çalıştırma manifesti yeniden
  oluşturur (yeniden oluşturulan manifest tüm dosyaları yeni sayar; bir sonraki çalışma her şeyi
  yeniden kopyalar — güvenlidir, yalnızca daha yavaştır).

**Simülasyon (`--dry-run`) kesinlikle sıfır yazma yapar.** `--dry-run` (hem tam yedekleme hem de
`--select --dry-run`) taramayı ve fark hesabını simüle edip *ne olacağını* yazdırır — hedef
dizinleri oluşturmaz, dosya kopyalamaz veya silmez, manifest (`.smartbackup_manifest.json` /
`.smartbackup_manifest.db`) oluşturmaz veya güncellemez, eski klasör düzenini taşımaz, sıkıştırma
arşivi üretmez ve `.log` dosyası yazmaz. Gerçek bir yedeklemeden hemen önce güvenle simülasyon
çalıştırabilirsiniz: hedef ortam tamamen dokunulmamış kalır ve sonraki gerçek çalıştırma bekleyen
tüm değişiklikleri görür.

### 3.2 Otomatik Harici Sürücü Algılama

`--target` vermediğinizde SmartBackup, platforma göre aday sürücüleri listeler:

| İşletim Sistemi | Yöntem | Neler listelenir? |
|---|---|---|
| **Windows** | Win32 `GetLogicalDrives` + `GetDriveTypeW` | *Çıkarılabilir (Removable)* veya *Sabit (Fixed)* türündeki mevcut **D:**–**Z:** sürücü harfleri (yedek: basit harf yoklaması) |
| **macOS** | `/Volumes` taraması | `Macintosh HD`, `Macintosh HD - Data`, `Macbook`, `Macbook - Data` ve gizli `.…` birimleri (`.timemachine` dahil) hariç tüm bağlı birimler |
| **Linux** | Bağlama noktası taraması | `/media/$USER`, `/run/media/$USER`, `/mnt` alt dizinleri |

Seçim kuralları (`DeviceDetector.find_backup_device`):

1. **100 MB'tan az boş alanı** olan sürücüler elenir.
2. `--label` (veya yapılandırmadaki `preferred_target`) bir sürücü etiketiyle — büyük/küçük harf
   duyarsız olarak — eşleşirse o sürücü doğrudan seçilir.
3. Yalnızca bir aday kaldıysa o kullanılır.
4. Birden fazla aday varsa hepsi listelenir ve **ilk sıradaki otomatik seçilir**. Belirli bir
   sürücüyü sabitlemek için `--label` veya `--target` kullanın.

> **Dikkat:** Windows ve Linux'ta *Sabit (Fixed)* diskler (ikincil dahili diskler) de aday
> sayılır. Birden fazla sürücü bağlıysa hedefi her zaman `--target PATH` veya `--label NAME` ile
> (ya da yapılandırmada `preferred_target` ayarlayarak) sabitleyin.

**Hiç sürücü bulunamazsa** SmartBackup şu seçenekleri sunar:

```
Options:
  [1] Create local temporary backup   → ~/.local_backup_temp klasörüne yazar
  [2] Wait and try again              → sürücüyü taktıktan sonra Enter'a basın (en fazla 3 deneme)
  [3] Cancel                          → yedekleme yapmadan çık
```

Şu anda kullanılabilir sürücüleri listelemek için:

```bash
smartbackup --list-drives
# tablo: No. | Label | Path | Free
```

### 3.3 Çoklu Cihaz Desteği (Makine Adı İzolasyonu)

Cihaz klasör adı `platform.node()` değerinden türetilir:

1. Alan adı soneki temizlenir (macOS mDNS `.local`, kurumsal FQDN'ler).
2. Alfanümerik, `-` veya `_` dışındaki tüm karakterler `-` ile değiştirilir, tekrarlar tekile
   indirgenir, uçlar kırpılır.
3. Geriye hiçbir şey kalmazsa `unknown-device` kullanılır.

Örnek: `Musabs-MacBook-Pro.local` → `Musabs-MacBook-Pro`.

```
YOUR_EXTERNAL_DRIVE/
└── Documents-Backup/
    ├── Musabs-MacBook-Pro/          ← bu bilgisayar (makine adına göre)
    │   ├── .smartbackup_manifest.json
    │   ├── _backup_logs/
    │   │   └── backup_20260924_093022.log
    │   └── ... dosyalarınız ...
    ├── Office-Desktop/              ← aynı diski paylaşan başka bir bilgisayar
    │   └── ...
    └── Musabs-MacBook-Pro_20260228_093022.zip   ← arşivler burada tutulur (bkz. §4)
```

- **Bir çalıştırma için adı geçersiz kılma:** `--device-name "Work-Laptop"`.
- **Eski düz klasör düzenleri** (dosyaların doğrudan `Documents-Backup/` altında durduğu yapı)
  bir sonraki yedekleme çalıştırmasında otomatik olarak `Documents-Backup/<hostname>/` altına
  taşınır.
- **Bir sürücüde hangi cihazların yedeği olduğunu görme:**
  `smartbackup --list-devices --target /path/to/drive` (tablo: Device | Files | Size | Last Backup).

### 3.4 Disk Üzerindeki Yedekleme Düzeni

```
<target>/
└── Documents-Backup/                     # sabit klasör adı (dahili seçenek: --backup-folder)
    ├── <Device>/                         # makine başına bir klasör
    │   ├── .smartbackup_manifest.json    # artımlı durum (veya --manifest-format sqlite ile .smartbackup_manifest.db)
    │   ├── _backup_logs/                 # çalıştırma başına bir günlük dosyası
    │   │   └── backup_YYYYMMDD_HHMMSS.log
    │   └── <aynalanmış kaynak ağacı>
    ├── <Device>_YYYYMMDD_HHMMSS.zip      # isteğe bağlı arşivler (--compress / `compress` ile)
    └── <Device>_YYYYMMDD_HHMMSS.tar.gz
```

Her gerçek çalıştırma; yapılandırmayı, özeti (dosya/boyut/süre/hız) ve dosya bazlı işlem listesini
(`[COPIED]`, `[UPDATED]`, `[SKIPPED]`, `[DELETED]`, `[ERROR]`) içeren bir günlük dosyası yazar.

### 3.5 Neler Hariç Tutulur?

Taranan her öğe için dört katman sırayla kontrol edilir (ilk eşleşme kazanır) ve **dosya/klasör
adına** karşı büyük/küçük harf duyarsız olarak değerlendirilir:

1. **Tam ad eşleşmesi** — örn. `node_modules`, `.git`, `venv`, `__pycache__`, `dist`, …
2. **Hariç tutulan uzantı** — `.pyc .pyo .pyd .class .o .obj .exe .dll .so .dylib .log .tmp .temp`
3. **Glob kalıbı** — `*`/`?` içeren kurallar düzenli ifadeye dönüştürülür:
   `*.egg-info`, `*.swp`, `*.swo`, `*.tmp`, `*.temp`, `*.log`, `*.bak`, `~*`
4. **Sanal ortam yapı algılama** — `pyvenv.cfg`, `Scripts/activate`, `bin/activate`,
   `Scripts/python.exe`, `bin/python` veya `lib/python3` içeren dizinler adından bağımsız olarak
   Python sanal ortamı sayılır ve atlanır.

Tam yerleşik liste [Ek B](#b-varsayılan-hariç-tutulanlar) bölümündedir. Özel kurallar için bkz.
[§7](#7-yapılandırma-ve-özel-hariç-tutma-kuralları).

### 3.6 Etkileşimli Seçmeli Klasör Yedekleme (`--select`)

`Documents` (veya `--source`) dizininizdeki üst düzey klasörlerin yalnızca bir alt kümesini
yedeklemek istediğinizde `--select` parametresini verin:

```bash
smartbackup --select
smartbackup --select --source ~/Documents --target /media/USB_DRIVE
smartbackup --select --dry-run                 # klasörleri seç ve diske hiç yazmadan önizle
smartbackup --select --manifest-format sqlite  # seçmeli yedekleme geçmişini SQLite'ta kaydet
```

**Etkileşimli klavye kontrolleri** (ek bağımlılık yok — yalnızca `rich` + Python standart kütüphanesi):

| Tuş | İşlev |
|---|---|
| `↑` / `↓` (veya `k` / `j`) | İmleci hareket ettir (büyük klasör listelerinde görünüm otomatik kayar) |
| `Space` | Vurgulanan klasörün onay kutusunu değiştir |
| `a` | Tümünü seç / tümünün seçimini kaldır |
| `Enter` | Seçimi onayla (en az 1 klasörün işaretli olmasını gerektirir) |
| `Esc` / `q` / `Ctrl+C` | Temiz şekilde iptal et (çıkış kodu `0`, yedekleme çalışmaz) |

**Garantiler ve denetim izi:**

- **Yalnızca klasörler, köke göreli yollar:** `--select`, gizli olmayan ve hariç tutulmayan üst
  düzey alt klasörleri listeler ve bunları `Documents-Backup/<Device>/<Klasör>/...` (köke göreli)
  altında aynalar; böylece seçmeli yedeklemeler tam yedeklemelerle ve `smartbackup restore` ile
  %100 uyumlu kalır.
- **Seçilmeyen klasörler ve kök dosyaları için tam koruma:** Seçmediğiniz klasörlerdeki dosyalar
  (ve kaynak kökündeki serbest dosyalar) hiçbir zaman silinmiş olarak işaretlenmez ve yedekleme
  diskinden değiştirilmez veya kaldırılmaz — JSON manifest, SQLite manifest ve `--no-manifest`
  modlarının tamamında geçerlidir.
- **Ayrılmış günlük ve manifest bölümleri:**
  - Yedekleme günlüklerinde `Mode: Selective (--select)` satırına ek olarak `SUMMARY:` bölümünden
    hemen önce özel bir `SELECTIVE BACKUP (--select)` bloğu ve numaralı `SELECTIVE WORKFLOW TRACE`
    akışı yer alır.
  - JSON manifestleri `last_backup_mode`, `last_selected_folders` ve `selective_backups` dizisini
    kaydeder; SQLite manifestleri seçmeli geçmişi `files` ve `metadata` tablolarından ayrı olarak
    özel bir **`selective_backups` tablosunda** saklar (JSON ↔ SQLite geçişlerinde korunur).
  - `smartbackup --show-manifest --target <path>` komutu `Last Backup Mode` bilgisini ve
    `Selective Backup History (--select)` tablosunu görüntüler.
- **Etkileşimli TTY gereklidir:** `--select` etkileşimli olmayan / yönlendirilmiş (piped) bir
  ortamda çağrılırsa çıkış kodu `1` ile hemen sonlanır.

---

## 4. CLI Komut Başvurusu ve Günlük Tarifler

### Komut ağacı

```
smartbackup [OPTIONS]                    # varsayılan eylem = yedekleme çalıştır
├── restore [OPTIONS]                    # yedekten dosya geri yükle
├── compress [OPTIONS]                   # mevcut bir yedeği arşivle
├── watch [OPTIONS]                      # ön planda sürücü izleyici
├── schedule [OPTIONS]                   # zamanlanmış yedekleme komutlarını yazdır
├── config                               # kalıcı yapılandırmayı görüntüle/güncelle
│   ├── list / get / set / unset
│   └── exclude / unexclude
└── daemon                               # arka plan izleyici servisi
    ├── install
    ├── status
    ├── uninstall
    └── clear-state
```

Her komut `--help` parametresini destekler (`smartbackup restore --help`, …).

### 4.1 Ana komut (`smartbackup`) seçenekleri

| Seçenek | Kısa | Argüman | Varsayılan | Açıklama |
|---|---|---|---|---|
| `--source` | `-s` | PATH | Documents klasörü | Yedeklenecek kaynak dizin |
| `--target` | `-t` | PATH | harici sürücü otomatik algıla | Hedef dizin/sürücü |
| `--label` | `-l` | TEXT | — | Tercih edilen hedef sürücü etiketi (algılamada büyük/küçük harf duyarsız eşleşir) |
| `--prompt` | | | kapalı | Algılanan sürücü için etkileşimli `[Y/n/d]` onay istemini çalıştır |
| `--select` | | | kapalı | Yedeklenecek üst düzey klasörleri seçmek için etkileşimli klavye menüsünü aç (TTY gerekir; bkz. [§3.6](#36-etkileşimli-seçmeli-klasör-yedekleme---select)) |
| `--dry-run` | | | kapalı | Sıfır yazma ile yedeklemeyi simüle et (dizin, dosya, manifest veya günlük oluşturulmaz; bkz. [§3.1](#31-artımlı-manifest-takibi)) |
| `--quiet` | `-q` | | kapalı | En az düzeyde çıktı (başlık + özet gösterilir; dosya bazlı günlükleme bastırılır) |
| `--exclude` | | TEXT (tekrarlanabilir) | — | Hariç tutma kalıbı ekle. **`config.json` dosyasına kaydedilir ve bu çalıştırmada uygulanır** — bkz. [§7.3](#73-özel-hariç-tutma-kuralları-ekleme) |
| `--list-drives` | | | — | Kullanılabilir harici sürücüleri listele ve çık |
| `--device-name` | | TEXT | otomatik algılanan hostname | Yedek alt klasörü için cihaz adı |
| `--list-devices` | | | — | Hedef sürücüde yedeği bulunan cihazları listele ve çık (`--target` gerekir) |
| `--no-manifest` | | | kapalı | Manifest takibini kapat (sürücüye karşı geleneksel boyut/mtime karşılaştırması) |
| `--manifest-format` | | FORMAT | yapılandırmadaki `manifest_format`, yoksa `json` | Manifest depolama arka ucu: `json` (`.smartbackup_manifest.json`) veya `sqlite` (`.smartbackup_manifest.db`) |
| `--show-manifest` | | | — | Manifest içeriğini ve seçmeli yedekleme geçmişini göster ve çık (`--target` gerekir) |
| `--verify` | | | — | Yedeği manifeste göre doğrula (kayıtlı özetler varsa yeniden hesaplar) ve çık (`--target` gerekir) |
| `--notify` | | | kapalı | Yedekleme tamamlandığında işletim sistemi masaüstü bildirimi gönder |
| `--compress` | | FORMAT | — | Kopyalama sonrasında yedeği sıkıştır: `zip` veya `tar.gz` |
| `--hash` | | | kapalı | **50 MB'a kadar** olan dosyalar için SHA-256 tabanlı değişiklik algılama |
| `--hash-all` | | | kapalı | Boyutundan bağımsız **tüm** dosyalar için SHA-256 (`--hash` içerir; daha yavaştır) |
| `--version` | `-v` | | — | `smartbackup 0.9.0` yazdır ve çık |
| `--help` | `-h` | | — | Yardım metnini göster ve çık |

### 4.2 Günlük tarifler

**Temel yedeklemeler**

```bash
smartbackup                                   # Documents → otomatik algılanan harici sürücü
python main.py                                # aynı işlem, kurulum gerekmez

smartbackup --source ~/Projects               # özel bir klasörü yedekle
smartbackup --target /media/USB_DRIVE         # açıkça belirtilen bir yola yedekle
smartbackup --target E:\                      # Windows örneği
smartbackup --label "MY_BACKUP_DISK"          # sürücüyü birim etiketine göre bul
smartbackup --device-name "Work-Laptop"       # özel cihaz alt klasör adı
smartbackup --quiet                           # minimal çıktı (betikler/CI)
```

**Çalıştırmadan önce önizleme**

```bash
smartbackup --dry-run                         # yedeklemeyi simüle et (hedefe sıfır yazma)
smartbackup --select                          # yedeklenecek klasörleri etkileşimli olarak seç
smartbackup --select --dry-run                # klasörleri seç ve hedefe hiç yazmadan önizle
smartbackup --list-drives                     # hangi sürücüler görünür durumda?
smartbackup --target /media/USB --list-devices      # bu diskte hangi makinelerin yedeği var?
smartbackup --target /media/USB --show-manifest     # manifest üst bilgi istatistikleri
```

**Bütünlük doğrulama (kademeli SHA-256 özetleme)**

```bash
smartbackup --hash                            # yedekleme sırasında ≤ 50 MB dosyalar için SHA-256 kaydet
smartbackup --hash-all                        # tüm dosyalar için SHA-256 kaydet (yavaş ama kapsamlı)
smartbackup --target /media/USB --verify      # varlık + boyut + kayıtlı özetleri yeniden denetle
```

Kademelerin çalışma biçimi:

- **Varsayılan (seçeneksiz):** değişiklik algılama yalnızca boyut + `mtime` kullanır.
- **`--hash`:** ≤ 50 MB dosyaların özeti (64 KB bloklarla) hesaplanıp manifeste kaydedilir; sonraki
  çalıştırmalarda boyut/mtime aynı görünse bile özet farkı dosyayı değişmiş sayar. Daha büyük
  dosyalar boyut/mtime karşılaştırmasına döner.
- **`--hash-all`:** boyut fark etmeksizin her dosyanın özeti hesaplanır. İçerik bütünlüğü hızdan
  önemliyse (bit-rot algılama, `mtime` güncellemeyen ağ sürücüleri) kullanın.
- **`--verify`:** yedeği bağımsız olarak yeniden okur ve `Missing:`, `Size mismatch:` ve
  `Hash mismatch:` hatalarını raporlar. Çıkış kodu `0` = temiz, `1` = sorun bulundu. Özet kontrolü
  yalnızca daha önce `--hash`/`--hash-all` ile özeti kaydedilmiş dosyalar için çalışır.

**Sıkıştırma**

```bash
smartbackup --compress zip                    # yedekle, ardından zip olarak arşivle
smartbackup --compress tar.gz                 # yedekle, ardından tar.gz olarak arşivle

# Daha önce tamamlanmış bir yedeği sonradan arşivle:
smartbackup compress --target /media/USB --format zip
smartbackup compress --target /media/USB --format tar.gz --device-name "Office-Desktop"
smartbackup compress --target /media/USB --format zip --remove-source   # başarı sonrası klasörü sil
```

- Arşivler `Documents-Backup/` içine `<Device>_<YYYYMMDD_HHMMSS>.zip|tar.gz` adıyla yazılır.
- Sıkıştırma yalnızca standart kütüphaneyi (`zipfile`/`tarfile`) atomik geçici-dosya + yeniden
  adlandırma yöntemiyle kullanır; başarısız bir çalışma yarım kalmış arşiv bırakmaz.
- `zip` DEFLATE kullanır ve boş dizinleri korur; `tar.gz` tar'ın yakaladığı her şeyi korur.
- `compress` alt komutu o cihaz için mevcut arşivler varsa uyarır ancak devam eder.
- Kök `--compress` seçeneği sıkıştırılmamış klasörü **silmez** — bunu yalnızca
  `compress --remove-source` yapar.

**Manifest yönetimi**

```bash
smartbackup --target /media/USB --show-manifest    # sürüm, biçim, kaynak, hostname, tarihler, toplamlar
smartbackup --target /media/USB --verify           # özet doğrulaması dahil
smartbackup --no-manifest                          # manifest takibini devre dışı bırak
```

### 4.3 `smartbackup restore` seçenekleri

| Seçenek | Kısa | Argüman | Açıklama |
|---|---|---|---|
| `--source` | `-s` | PATH | **Zorunlu.** `Documents-Backup/` klasörünü *içeren* sürücü/dizin |
| `--target` | `-t` | PATH | Geri yükleme hedefi (varsayılan: manifestte kayıtlı orijinal kaynak yolu) |
| `--pattern` | `-p` | TEXT (tekrarlanabilir) | Göreli yola karşı (`fnmatch`) eşleşen glob filtreleri, örn. `"*.py"` |
| `--overwrite` | | | Mevcut dosyaların üzerine yaz (`--conflict overwrite` için eski takma ad) |
| `--conflict` | | TEXT | Çakışma stratejisi: `skip` (varsayılan), `overwrite`, `newer`, `rename`. `--overwrite`'a göre önceliklidir |
| `--dry-run` | | | Hiçbir dosya kopyalamadan geri yüklemeyi önizle |
| `--list` | | | Yedekteki dosyaları listele ve çık |
| `--manifest-info` | | | Manifest meta veri özetini tablo olarak göster ve çık |
| `--device-name` | | TEXT | Geri yüklenecek cihaz alt klasörü (varsayılan: otomatik algılanan hostname, sonra eski düzen) |

### 4.4 `smartbackup compress` seçenekleri

| Seçenek | Kısa | Argüman | Varsayılan | Açıklama |
|---|---|---|---|---|
| `--target` | `-t` | PATH | *zorunlu* | `Documents-Backup/` içeren yedekleme sürücüsü/dizini |
| `--format` | `-f` | TEXT | `zip` | `zip` veya `tar.gz` (başka bir değer → hata, çıkış kodu `1`) |
| `--device-name` | | TEXT | otomatik hostname | Sıkıştırılacak cihaz klasörü |
| `--remove-source` | | | kapalı | Arşiv oluşturulduktan sonra sıkıştırılmamış klasörü sil |
| `--backup-folder` | | TEXT | `Documents-Backup` | *Gizli/dahili* yedek klasörü adı |

### 4.5 `smartbackup watch` seçenekleri

| Seçenek | Kısa | Argüman | Varsayılan | Açıklama |
|---|---|---|---|---|
| `--interval` | `-i` | FLOAT | `2.5` | Yoklama aralığı (saniye) |
| `--cooldown` | `-c` | INTEGER | yapılandırmadaki `auto_watch_cooldown`, yoksa `300` | Aynı sürücü için istemler arası bekleme süresi (saniye); komut satırı seçeneği yapılandırmayı ezer |

### 4.6 `smartbackup config` alt komutları

| Komut | Açıklama |
|---|---|
| `smartbackup config list` | Tüm anahtarları, değerlerini (veya `(not set)`) ve yapılandırma dosya yolunu göster |
| `smartbackup config get <key>` | Tek bir anahtarın değerini yazdır |
| `smartbackup config set <key> <value>` | Tek bir değeri doğrula ve kaydet |
| `smartbackup config unset <key>` | Anahtarı kaldırarak varsayılana dön |
| `smartbackup config exclude <pattern>...` | Özel hariç tutma kalıpları ekle |
| `smartbackup config unexclude <pattern>...` | Özel hariç tutma kalıplarını kaldır |

Desteklenen anahtarlar: `preferred_target`, `device_name` (dosya sistemine uygun klasör adına
temizlenir), `auto_watch_cooldown` (tam sayı ≥ 0), `preferred_terminal`, `manifest_format` (`json`
veya `sqlite`) ve `exclusions` (yalnızca `exclude`/`unexclude` üzerinden yönetilir). Bilinmeyen
anahtarlar geçerli listeyi yazdırarak `1` çıkış koduyla sonlanır.

```bash
smartbackup config set auto_watch_cooldown 60
smartbackup config set device_name "Work Laptop"    # Work-Laptop olarak kaydedilir
smartbackup config set preferred_target MY_BACKUP_DISK
smartbackup config set manifest_format sqlite
smartbackup config exclude "*.iso" "LargeDatasets"
smartbackup config unexclude "*.iso"
smartbackup config list
```

### 4.7 `smartbackup daemon` alt komutları

| Komut | Açıklama |
|---|---|
| `smartbackup daemon install` | İşletim sistemi arka plan izleyici servisini kaydet **ve başlat** |
| `smartbackup daemon status` | Kurulum / Durum (PID dahil) / Servis Yolu / Ayrıntılar bilgisini göster |
| `smartbackup daemon uninstall` | Arka plan servisini durdur ve kaldır |
| `smartbackup daemon clear-state` | İzleyici bekleme durumunu (`watcher_state.json`) temizle |

Seçenek almaz; ayrıntılar [§5](#5-otomatik-algılama-servisi-ve-izleyici-kılavuzu) bölümündedir.

### 4.8 Çıkış kodları

| Kod | Anlamı |
|---|---|
| `0` | Başarılı (ayrıca: dry-run/list/manifest işlemleri, `--select` veya `--prompt` kullanıcı iptali, Ctrl+C ile izleyici durdurma) |
| `1` | Hata: yedekleme hataları, doğrulama hataları, etkileşimli TTY olmadan `--select` çağrısı, geçersiz `--compress`/`--manifest-format`, eksik dizinler, eksik zorunlu `--target`/`--source` |
| `130` | Yedekleme sırasında Ctrl+C ile kesildi |

---

## 5. Otomatik Algılama Servisi ve İzleyici Kılavuzu

SmartBackup bir *sürücü izleyicisi* olarak çalışabilir: yeni takılan sürücüleri periyodik olarak
kontrol eder ve bilinen bir yedekleme sürücüsü algılandığında yerel bir terminal penceresi açarak
yedeklemeyi başlatmak isteyip istemediğinizi sorar.

### 5.1 Bir sürücü nasıl "SmartBackup hedefi" olarak tanınır?

Bir sürücü yalnızca aşağıdaki koşullardan **herhangi biri** sağlanırsa izleyiciyi tetikler (`DriveMatcher`):

1. Etiketi yapılandırmadaki `preferred_target` (veya verilen etiket) ile eşleşiyorsa, veya
2. `Documents-Backup/<hostname>/.smartbackup_manifest.json` (veya `.smartbackup_manifest.db`) mevcutsa, veya
3. `Documents-Backup/<hostname>/` klasörü mevcutsa, veya
4. Eski düz yerleşim: `Documents-Backup/.smartbackup_manifest.json` (veya `.db`) mevcutsa.

> **Önemli:** Yepyeni, boş bir sürücü hiçbir zaman otomatik eşleşmez (henüz manifest yoktur).
> Bir kez elle `smartbackup --target /path/to/drive` çalıştırarak sürücüyü tanıtın; sonrasında
> izleyici sürücüyü otomatik olarak tanıyacaktır.

Kilitli veya okunamayan birimler (örn. Windows'ta BitLocker ile kilitli diskler) güvenle yönetilir:
izin ve işletim sistemi hataları yakalanır, sürücü hedef değilmiş gibi geçilir ve izleyici çalışmaya
devam eder.

### 5.2 Ön planda test etme: `smartbackup watch`

```bash
smartbackup watch                          # aralık 2.5 sn, bekleme 300 sn
smartbackup watch --interval 1.0           # her saniye kontrol et
smartbackup watch --cooldown 60            # aynı sürücü için dakikada en fazla bir istem
```

Durum paneli (`SmartBackup Drive Watcher Active`, yoklama aralığı ve bekleme süresiyle) görüntülenir.
**Ctrl+C** ile durdurabilirsiniz (çıkış kodu `0`).

İzleyici başladığında bağlı sürücülerin bir **başlangıç anlık görüntüsünü** alır; bu nedenle zaten
takılı olan sürücüler istem açmaz — yalnızca *sonradan takılanlar* tetiklenir.

### 5.3 Etkileşimli istem `[Y/n/d]`

Eşleşen bir sürücü algılandığında SmartBackup şu komutu çalıştıran yeni bir yerel terminal penceresi açar:

```
python -m smartbackup --target <drive-path> --prompt
```

*(Bağımsız ikili dosya kullanılıyorsa doğrudan `<smartbackup-binary> --target <drive-path> --prompt` çalıştırılır.)*

Sürücü yolu, boş/toplam kapasite, kaynak klasör ve cihaz kimliğini içeren bir panel basılır ve sorulur:

```
Start backup now? (Y/n/d) [y]:
```

| Giriş | Kabul edilen biçimler | Sonuç |
|---|---|---|
| **Evet** | `y`, `yes`, *(Enter)* | Normal yedekleme başlar |
| **Hayır** | `n`, `no` | "Backup skipped by user." — çıkış kodu `0` |
| **Simülasyon** | `d`, `dry-run`, `dryrun` | Sıfır yazmalı simülasyon modunda çalışır |
| Başka bir değer | — | Uyarı yazdırılır ve **standart yedekleme** ile devam edilir |
| Ctrl+C | — | "Backup cancelled by user." — çıkış kodu `0` |

Çalıştırma bittikten sonra istem pencereleri `Window will close automatically in 5 seconds...`
mesajını gösterir.

**İstemler tekrar önleme (debounce) korumasına sahiptir:**

- **3 saniyelik genel bastırma** — aynı anda bağlanan çok bölümlü diskler tek bir pencere açar.
- **Sürücü başına bekleme süresi** (varsayılan `300` sn / 5 dakika) — aynı sürücüyü çıkarıp hemen
  tekrar takmak süre dolmadan yeniden pencere açmaz.
- Durum `<config dir>/watcher_state.json` içinde saklanır. *Anında yeniden istem zorlamak için*
  `smartbackup daemon clear-state` çalıştırın.

**İstem penceresi için kullanılan terminal sırası:**

| İşletim Sistemi | Deneme sırası |
|---|---|
| Windows | Windows Terminal (`wt.exe --title …`) → `cmd.exe` `start` → PowerShell `-NoExit` |
| macOS | iTerm2 (`preferred_terminal` = `iterm`/`iterm2` ise) → AppleScript ile Terminal.app → `open -a Terminal.app` yedeği |
| Linux | Yapılandırmadaki `preferred_terminal` → `x-terminal-emulator` → `gnome-terminal` → `kitty` → `alacritty` → `konsole` → `xfce4-terminal` → `xterm` |

**Ekransız (headless) ortamlar** (`DISPLAY`/`WAYLAND_DISPLAY` olmayan Linux veya SSH oturumları)
pencere açmaz; izleyici sessiz kalır. İstem modunu elle çalıştırabilirsiniz:

```bash
smartbackup --target /path/to/drive --prompt
```

### 5.4 Arka plan servisi: `smartbackup daemon`

```bash
smartbackup daemon install      # izleyici servisini kaydet + başlat
smartbackup daemon status       # Kurulu mu? Çalışıyor mu (PID)? Servis dosyası nerede?
smartbackup daemon clear-state  # bekleme durumunu sıfırla
smartbackup daemon uninstall    # durdur + kaldır
```

Her platformda oluşturulan servis bileşeni:

| İşletim Sistemi | Bileşen | Ayrıntılar |
|---|---|---|
| **Windows** | Zamanlanmış Görev `SmartBackupWatcher` | Tetikleyici: *oturum açılışında* (`/sc onlogon /rl highest`); kurulumda hemen başlatılır |
| **macOS** | LaunchAgent `~/Library/LaunchAgents/com.smartbackup.watcher.plist` | `RunAtLoad` + `KeepAlive` (otomatik yeniden başlatma); stdout → `~/.config/smartbackup/logs/watcher.log`, stderr → `watcher.err.log` |
| **Linux** | systemd **kullanıcı** birimi `~/.config/systemd/user/smartbackup-watcher.service` | `Type=simple`, `Restart=always`, `RestartSec=5s` |

Notlar:

- Kurulum sırasında hangi Python yorumlayıcısı (veya bağımsız çalıştırılabilir dosya) kullanıldıysa
  servis ona bağlanır — sonradan sileceğiniz geçici bir sanal ortamdan kurmayın.
- **Windows:** arka plan görevi görünür pencere olmadan çalışır; yalnızca sürücü algılandığında
  istem penceresi açılır.
- **Linux:** systemd *kullanıcı* birimleri yalnızca oturum açıldığında başlar; oturum açılmadan
  da çalışması için `loginctl enable-linger $USER` etkinleştirin.
- Kaldırma işlemi idempotenttir: servis zaten yoksa hata vermeden bilgi mesajıyla tamamlanır.

### 5.5 İşletim sistemiyle periyodik yedekleme zamanlama

Windows Görev Zamanlayıcı, macOS `launchd` veya Linux `cron`/`systemd` için işletim sisteminize
özel kurulum komutlarını yazdırmak üzere `smartbackup schedule [--hours N]` (varsayılan: 24 saat)
çalıştırın. Dilerseniz elle de kurabilirsiniz:

**Windows (Görev Zamanlayıcı — *Yönetici* isteminde çalıştırın):**

```powershell
schtasks /create /tn "SmartBackup" /tr "smartbackup" /sc daily /st 09:00
```

**macOS (`~/Library/LaunchAgents/com.smartbackup.plist`, ardından `launchctl load`):**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>com.smartbackup</string>
    <key>ProgramArguments</key>
    <array>
        <string>/path/to/python</string><string>-m</string><string>smartbackup</string>
    </array>
    <key>StartInterval</key><integer>86400</integer>
    <key>RunAtLoad</key><true/>
</dict>
</plist>
```

**Linux (cron):**

```cron
0 9 * * * /path/to/python -m smartbackup
```

**Linux (systemd kullanıcı zamanlayıcısı):** `~/.config/systemd/user/smartbackup.service` +
`~/.config/systemd/user/smartbackup.timer`, ardından `systemctl --user enable --now smartbackup.timer`.

> Periyodik *yedekleme zamanlamak*, *izleyici servisinden* (§5.4) farklıdır. İzleyici servisi
> yalnızca disk bağlantılarını algılar; zamanlayıcıya göre otomatik yedekleme çalıştırmaz.

---

## 6. Veri Kurtarma ve Geri Yükleme Kılavuzu

### 6.1 Temel mantık

`restore` komutu için `--source`, **`Documents-Backup/` klasörünü içeren sürücü (veya dizin)**
olmalıdır — yani yedeklemede `--target` olarak verdiğiniz yolun aynısı — cihaz alt klasörünün
kendisi *değildir*:

```
smartbackup restore --source /media/USB_DRIVE             # ✅  sürücü kökü
smartbackup restore --source /media/USB_DRIVE/My-Laptop   # ❌  yanlış: Documents-Backup/ kendiliğinden eklenir
```

`--source/Documents-Backup/` içindeki cihaz çözümleme sırası:

1. `--device-name` (verildiyse), yoksa
2. Eski düz düzen (manifest doğrudan `Documents-Backup/` altındaysa), yoksa
3. `Documents-Backup/<mevcut-hostname>/` klasörü varsa, yoksa
4. Kök klasörün kendisi.

**Hedef:** `--target` verildiyse orası; aksi halde **manifestte kayıtlı orijinal kaynak yolu**
(örn. `/home/you/Documents`). İkisi de yoksa geri yükleme
`No target path specified and no manifest source found` hatasıyla sonlanır.

### 6.2 Adım 1 — Geri yüklemeden önce inceleyin

```bash
# İçeriği listele (manifestten veya manifest yoksa dizin taramasıyla)
smartbackup restore --source /media/USB_DRIVE --list

# Manifest özeti: kaynak yolu, hostname, tarihler, toplamlar
smartbackup --target /media/USB_DRIVE --show-manifest
smartbackup restore --source /media/USB_DRIVE --manifest-info

# Bütünlük denetimi: varlık + boyut + kayıtlı özetler
smartbackup --target /media/USB_DRIVE --verify

# Çalıştırma başına denetim günlüğü
cat /media/USB_DRIVE/Documents-Backup/<Device>/_backup_logs/backup_*.log
```

### 6.3 Adım 2 — Geri yükleyin

```bash
# Orijinal konumuna tam geri yükleme (manifest.source üzerinden)
smartbackup restore --source /media/USB_DRIVE

# Özel bir dizine geri yükleme (test veya yeni makine düzeni için ideal)
smartbackup restore --source /media/USB_DRIVE --target ~/Restored

# Paylaşılan bir sürücüdeki belirli bir makinenin yedeğinden geri yükleme
smartbackup restore --source /media/USB_DRIVE --device-name "Office-Desktop"

# Glob kalıplarıyla filtreleme (göreli yola göre; tekrarlanabilir)
smartbackup restore --source /media/USB_DRIVE --pattern "*.py" --pattern "*.md"

# Önizleme — hiçbir dosya kopyalanmaz
smartbackup restore --source /media/USB_DRIVE --dry-run

# Yerelde zaten bulunan dosyaların üzerine yaz
smartbackup restore --source /media/USB_DRIVE --overwrite
```

Bilinmesi faydalı iç ayrıntılar:

- Dosyalar meta verileriyle birlikte (`copy2`) **atomik geçici dosya + yeniden adlandırma**
  yöntemiyle kopyalanır; kesintiye uğrayan bir geri yükleme yarım yazılmış dosya bırakmaz.
- Geri yükleme çok iş parçacıklı çalışır (4 işçi).
- Dahili kayıt dosyaları asla geri yüklenmez: `_backup_logs/` altındaki her şey ve `.smartbackup*`
  dosyaları atlanır.
- Tamamlandığında `RESTORE SUMMARY` tablosu basılır (`errors == 0` ise çıkış kodu `0`, aksi halde `1`).

### 6.4 Çakışma çözümleme stratejileri

Hedef dosya yerelde zaten mevcutsa:

| Strateji | Davranış | Kullanım |
|---|---|---|
| **SKIP** | Mevcut yerel dosyayı koru; `Skipped ("File exists")` olarak say | ✅ **Varsayılan** (seçeneksiz veya `--conflict skip`) |
| **OVERWRITE** | Yerel dosyayı yedekteki sürümle değiştir | ✅ `--conflict overwrite` (veya eski `--overwrite`) |
| **NEWER** | Yalnızca yedekteki kopyanın `mtime` değeri yerel dosyadan yeniyse üzerine yaz; aksi halde atla | ✅ `--conflict newer` |
| **RENAME** | İkisini de koru: yerel dosya yerinde kalır, geri yüklenen kopya yanına `<ad>.restored-<YYYYmmdd-HHMMSS>.<uzantı>` adıyla yazılır (çakışmada `-1`, `-2`, … eklenir) | ✅ `--conflict rename` |

> Hem `--conflict` hem `--overwrite` verilirse `--conflict` kazanır. Bilinmeyen bir `--conflict`
> değeri geçerli stratejileri listeleyerek çıkış kodu `1` ile sonlanır.

### 6.5 Sıkıştırılmış arşivden geri yükleme

`restore` yalnızca **dizinleri** okur, `.zip`/`.tar.gz` dosyalarını doğrudan okumaz. Arşivlenmiş
bir yedeği geri yüklemek için önce beklenen klasör düzenine çıkarın:

```bash
# 1. Cihaz klasörüne çıkarın
mkdir -p /media/USB_DRIVE/Documents-Backup/<Device>
unzip <Device>_<timestamp>.zip -d /media/USB_DRIVE/Documents-Backup/<Device>       # zip
tar -xzf <Device>_<timestamp>.tar.gz -C /media/USB_DRIVE/Documents-Backup/<Device> # tar.gz

# 2. Normal şekilde geri yükleyin
smartbackup restore --source /media/USB_DRIVE --device-name "<Device>"
```

### 6.6 Farklı bir bilgisayarda geri yükleme

Cihaz klasörleri makine adına göredir; dolayısıyla başka bir bilgisayar klasörünüzü otomatik
bulamaz. Şu şekilde belirtin:

```bash
smartbackup restore --source /media/USB_DRIVE --device-name "Old-Machine-Name"
```

…veya açık bir dizine geri yüklemek için `--target` ekleyin. İçeriği doğrulamak için önce `--list` çalıştırın.

### 6.7 Yaygın geri yükleme hataları

| Mesaj | Nedeni | Çözüm |
|---|---|---|
| `Backup directory not found: …` | `--source`, `Documents-Backup/` içine veya cihaz klasörüne işaret ediyor | **Sürücü kökünü** verin |
| `No manifest found` + her şey taramayla listeleniyor | Yanlış cihaz klasörü veya eski düzen | `--device-name` kullanın ya da `--list` ile kontrol edin |
| `No target path specified and no manifest source found` | `--target` verilmemiş ve manifestte `source` yok | `--target <dizin>` verin |
| Hiçbir şey geri yüklenmedi, `No files to restore!` | Kalıp çok dar veya yalnızca dahili dosyalar var | `--pattern` filtresini genişletin, `--list` ile doğrulayın |
| Dosya başına `Permission denied` | İşletim sistemi izinleri / korumalı klasörler | Sahibi olduğunuz bir dizine geri yükleyin (`--target ~/Restored`) |

---

## 7. Yapılandırma ve Özel Hariç Tutma Kuralları

### 7.1 Yapılandırma dosyası nerede bulunur?

| İşletim Sistemi | Yol |
|---|---|
| **Windows** | `%APPDATA%\SmartBackup\config.json` (genellikle `C:\Users\<kullanıcı>\AppData\Roaming\SmartBackup\config.json`) |
| **macOS** | `~/.config/smartbackup/config.json` |
| **Linux** | `~/.config/smartbackup/config.json` |

Dosya ilk yazmada oluşturulur. Yapılandırma dizini ayrıca `watcher_state.json` (bekleme durumu)
ve macOS'ta servis günlüklerini (`logs/watcher.log`, `logs/watcher.err.log`) barındırır.

### 7.2 Yapılandırma anahtarları

| Anahtar | Tür | Varsayılan | Etkisi | CLI'dan ayarlanabilir mi? |
|---|---|---|---|---|
| `exclusions` | dize listesi | `[]` (yerleşiklerle birleştirilir) | Özel hariç tutma kalıpları | ✅ `--exclude` ekler ve uygular; `config exclude` / `config unexclude` yönetir |
| `preferred_target` | dize | yok | Hedef seçiminde ve izleyici eşleşmesinde kullanılan sürücü etiketi (büyük/küçük harf duyarsız) | ✅ `config set preferred_target` |
| `device_name` | dize | yok (hostname kullanılır) | Otomatik algılanan cihaz adını geçersiz kılar | ✅ `config set device_name` (temizlenir); `--device-name` yalnızca tek çalıştırmalık |
| `auto_watch_cooldown` | tam sayı (sn) | `300` | İzleyici bekleme süresi | ✅ `config set auto_watch_cooldown`; `watch --cooldown` tek çalıştırmalık ezer |
| `preferred_terminal` | dize | yok | İstem pencereleri için terminal: macOS'ta `iterm`/`iterm2`, Linux'ta herhangi bir terminal ikili adı | ✅ `config set preferred_terminal` |
| `manifest_format` | dize | `json` | Manifest depolama arka ucu (`json` veya `sqlite`) | ✅ `config set manifest_format`; `--manifest-format` tek çalıştırmalık ezer |

Örnek `config.json`:

```json
{
  "exclusions": ["*.iso", "Downloads", "LargeDatasets"],
  "preferred_target": "MY_BACKUP_DISK",
  "device_name": "Work-Laptop",
  "auto_watch_cooldown": 300,
  "preferred_terminal": "iTerm2",
  "manifest_format": "sqlite"
}
```

### 7.3 Özel Hariç Tutma Kuralları Ekleme

**CLI üzerinden:**

```bash
smartbackup --exclude "*.iso" "Downloads" "LargeDatasets"
```

Her `--exclude` değeri `config.json` dosyasına **kalıcı olarak kaydedilir** ve **hemen bu
çalıştırmada uygulanır** (`ConfigManager.get_exclusions()` = yerleşik varsayılanlar + özel
kalıplarınız). Sonraki çalıştırmalar seçeneği tekrar vermeseniz de bu kalıpları uygular.

**Kayıtlı bir kalıbı kaldırma:** `smartbackup config unexclude "*.iso"` (veya `config.json`
içindeki `exclusions` dizisini düzenleyerek).

### 7.4 Tercih edilen yedekleme birimini tanımlama (`preferred_target`)

Her seferinde `--target` yazmadan "*her zaman bu sürücüyü kullan*" demek (ve izleyicinin bu
sürücüyü tanımasını sağlamak) için:

1. Etiketi öğrenin: `smartbackup --list-drives` (**Label** sütunu).
2. Kaydedin: `smartbackup config set preferred_target MY_BACKUP_DISK` (veya `config.json` içine yazın).
3. Eşleşme büyük/küçük harf duyarsızdır; Windows sürücü harflerini (`E:` / `E:\`) ve macOS/Linux
   birim adlarını anlar.

Tek seferlik (kalıcı olmayan) eşdeğeri: `smartbackup --label "MY_BACKUP_DISK"`.

---

## 8. Platform Ayrıntıları ve Sorun Giderme

### 8.1 Windows

- **BitLocker ile kilitli sürücüler:** Kilitli bir birim sorgulandığında `PermissionError`/`OSError`
  üretir. `DriveMatcher` bunları güvenle yakalar ve sürücüyü hedef dışı sayar — izleyici çökmez,
  ancak **sürücünün kilidini açana kadar istem görünmez**. Önce kilidi açın (`manage-bde -unlock D: -password`
  veya Dosya Gezgini).
- **Terminal geri dönüş sırası:** İstem pencereleri önce Windows Terminal (`wt.exe`), sonra
  `cmd.exe` `start`, ardından PowerShell `-NoExit` dener. Hiçbiri açılmazsa elle çalıştırın:
  `python -m smartbackup --target E:\ --prompt`.
- **Sürücü harfleri:** Algılama **D:**–**Z:** arasını yoklar; sistem diskiniz (`C:`) asla otomatik
  hedef seçilmez.
- **Eski konsol kodlama hataları:** SmartBackup artık UTF-8 yeniden yapılandırmasını otomatik
  dener (`ensure_utf8_console()`); çok eski konsollarda yine de sorun yaşarsanız Windows Terminal
  kullanın veya `$env:PYTHONUTF8="1"; smartbackup` ile çalıştırın.

### 8.2 macOS

- **Terminal öykünmesi:** Varsayılan olarak AppleScript üzerinden **Terminal.app** açılır. **iTerm2**
  için `smartbackup config set preferred_terminal iterm2` ayarlayın.
- **Sistem / Time Machine hariç tutmaları:** `/Volumes` taraması `Macintosh HD`, `Macintosh HD - Data`,
  `Macbook`, `Macbook - Data`, gizli birimler ve `.timemachine` bağlamalarını otomatik atlar.
- **İzinler (TCC):** Tarama `Permission denied` bildiriyorsa *Sistem Ayarları → Gizlilik ve
  Güvenlik → Tam Disk Erişimi* altından terminal uygulamanıza (Terminal.app / iTerm2) izin verip
  terminali yeniden başlatın.
- **Otomasyon onayları:** İlk `osascript` çağrısı macOS otomasyon izin penceresi açabilir.

### 8.3 Linux

- **Bağlama noktaları:** Harici ortamlar `/media/$USER`, `/run/media/$USER` ve `/mnt` altında aranır.
  Dağıtımınız başka bir yere bağlıyorsa `--target /baglama/noktaniz` verin.
- **systemd kullanıcı birimleri:** `daemon install`, `~/.config/systemd/user/smartbackup-watcher.service`
  dosyasını yazar ve `systemctl --user daemon-reload` + `enable --now` çalıştırır. Kullanıcı Oturum
  D-Bus'ı yoksa terminalde `smartbackup watch` kullanın.
- **Headless / SSH:** `DISPLAY`/`WAYLAND_DISPLAY` yoksa izleyici GUI penceresi açmayı atlar.
- **İzinler:** Başlamadan önce hedefte yazma testi yapılır; `No write permissions on backup medium`
  hatası salt okunur bağlama veya `root` sahipliği anlamına gelir.

### 8.4 Sorun giderme tablosu

| Belirti | Olası neden | Çözüm |
|---|---|---|
| `EXTERNAL STORAGE MEDIUM NOT FOUND` | ≥ 100 MB boş alana sahip uygun sürücü yok / bağlı değil | `--list-drives`; bağlantıyı kontrol edin; `--target` verin veya geçici yerel yedek (`[1]`) seçin |
| Yedek beklenmeyen bir diske gitti | Birden fazla aday sürücü vardı, ilki seçildi | `--target` veya `--label` / `preferred_target` ile sabitleyin |
| `Please specify backup directory with --target` | `--list-devices`, `--show-manifest` veya `--verify` `--target` olmadan çağrıldı | `--target <sürücü kökü>` ekleyin |
| İzleyici çalışıyor ama **istem açmıyor** | Yeni/boş sürücü (§5.1 ile eşleşmiyor), bekleme süresi aktif veya headless ortam | Sürücüye bir kez elle yedekleme yapın; `smartbackup daemon clear-state` çalıştırın; `daemon status` kontrol edin |
| İkinci yedekleme *her şeyi* yeniden kopyalıyor | Manifest eksik/bozuk veya `--no-manifest` kullanıldı | Normal kurtarma davranışıdır — manifest yeniden oluşur; tekrarlıyorsa disk sağlığını kontrol edin |
| `Full metadata copy failed … Falling back to basic copy` | ExFAT/FAT32 tam POSIX meta verilerini desteklemiyor | Beklenen durumdur; `mtime` elle korunur |
| `The --select option requires an interactive terminal (TTY)` | `--select` yönlendirilmiş/etkileşimsiz kabukta veya CI'da çağrıldı | Etkileşimli bir terminalde çalıştırın veya `--select` kullanmayın |
| `Storage medium error (drive may have been disconnected)` | Yedekleme ortasında sürücü çıkarıldı | Yeniden takıp tekrar çalıştırın; önceden kopyalananlar manifestte izlenir |
| Geri yükleme hiçbir şey bulamıyor | `--source` sürücü kökü yerine cihaz klasörüne işaret ediyor | Sürücü kökünü verin (§6.1) |
| Servis Python/venv yenilendikten sonra durdu | Servis eski yorumlayıcı yoluna kayıtlı | Aktif ortamdan `smartbackup daemon uninstall` ve ardından `install` çalıştırın |

### 8.5 Bilinen sınırlamalar (mevcut sürüm)

1. `restore` yalnızca dizinleri işler — arşivleri önce çıkarın (§6.5).
2. Şifreleme, tekilleştirme, sürümleme veya uzak hedefler henüz yoktur (§1).
3. `--select` şu anda yalnızca üst düzey klasörler üzerinde çalışır (kök dizindeki tekil dosyalar değil).

---

## 9. Ekler

### A. Hızlı seçenek kartı

```text
smartbackup [OPTIONS]
  -s, --source PATH        Kaynak dizin (varsayılan: Documents)
  -t, --target PATH        Hedef sürücü/dizin (varsayılan: otomatik algıla)
  -l, --label TEXT         Tercih edilen hedef sürücü etiketi
      --prompt             Etkileşimli [Y/n/d] onay istemi modu
      --select             Etkileşimli klasör seçici (üst düzey klasörler, TTY gerekir)
      --dry-run            Simüle et (sıfır yazma: dizin, dosya, manifest veya günlük yok)
  -q, --quiet              Minimal çıktı
      --exclude TEXT       Ek hariç tutma kalıbı (config.json'a kaydedilir)
      --list-drives        Sürücüleri göster ve çık
      --list-devices       --target üzerindeki cihazları göster ve çık
      --device-name TEXT   Cihaz alt klasörü (varsayılan: hostname)
      --show-manifest      --target için manifest özetini göster ve çık
      --verify             Yedeği manifeste göre doğrula ve çık
      --no-manifest        Manifest takibini devre dışı bırak
      --manifest-format    json | sqlite (varsayılan: config manifest_format, yoksa json)
      --notify             Tamamlandığında masaüstü bildirimi gönder
      --compress FORMAT    Kopyalama sonrası zip | tar.gz sıkıştırma
      --hash               ≤ 50 MB dosyalar için SHA-256
      --hash-all           Tüm dosyalar için SHA-256
  -v, --version            Sürümü yazdır ve çık

smartbackup restore  -s PATH [-t PATH] [-p GLOB]... [--conflict skip|overwrite|newer|rename] [--overwrite] [--dry-run] [--list] [--manifest-info] [--device-name TEXT]
smartbackup compress -t PATH [-f zip|tar.gz] [--device-name TEXT] [--remove-source]
smartbackup watch    [-i SECONDS] [-c SECONDS]
smartbackup schedule [--hours N]
smartbackup config   list | get KEY | set KEY VALUE | unset KEY | exclude PATTERN... | unexclude PATTERN...
smartbackup daemon   install | status | uninstall | clear-state
```

### B. Varsayılan Hariç Tutulanlar

**Klasör/dosya adları** (büyük/küçük harf duyarsız tam eşleşme):

<details>
<summary><code>DEFAULT_EXCLUSIONS</code> (genişletmek için tıklayın)</summary>

- **Node.js / JavaScript:** `node_modules`, `.npm`, `.yarn`, `bower_components`, `.next`,
  `.nuxt`, `dist`, `build`, `.parcel-cache`
- **Python:** `__pycache__`, `.pytest_cache`, `.mypy_cache`, `.tox`, `.nox`, `venv`,
  `.venv`, `env`, `.env`, `ENV`, `.eggs`, `.Python`, `pip-wheel-metadata`, `.pytype`
- **Python paketleme/sanal ortamlar:** `*.egg-info`, `virtualenv`, `.virtualenv`, `pipenv`,
  `.pipenv`, `conda-env`, `.conda`
- **JVM:** `target`, `.gradle`, `.m2`
- **.NET:** `bin`, `obj`, `packages`
- **Go:** `vendor`
- **IDE/düzenleyici:** `.idea`, `.vscode`, `*.swp`, `*.swo`, `.project`, `.settings`, `.classpath`
- **Sürüm kontrolü:** `.git`, `.svn`, `.hg`
- **İşletim sistemi artıkları:** `.DS_Store`, `Thumbs.db`, `desktop.ini`
- **Geçici dosyalar:** `*.tmp`, `*.temp`, `*.log`, `*.bak`, `~*`
- **Önbellekler:** `.cache`, `cache`, `.sass-cache`
- **Docker:** `.docker`

</details>

**Hariç tutulan uzantılar** (her zaman atlanır):
`.pyc` `.pyo` `.pyd` `.class` `.o` `.obj` `.exe` `.dll` `.so` `.dylib` `.log` `.tmp` `.temp`

**Ayrıca:** Yapısal olarak Python sanal ortamı olduğu algılanan tüm dizinler (§3.5, 4. katman).

### C. Temel dosya yolları

| Öğe | Yol |
|---|---|
| Yapılandırma (Windows) | `%APPDATA%\SmartBackup\config.json` |
| Yapılandırma (macOS/Linux) | `~/.config/smartbackup/config.json` |
| İzleyici bekleme durumu | `<config dir>/watcher_state.json` |
| İzleyici servis günlükleri (macOS) | `~/.config/smartbackup/logs/watcher.log`, `watcher.err.log` |
| Yedekleme manifesti | `<target>/Documents-Backup/<Device>/.smartbackup_manifest.json` (veya `.db`) |
| Yedekleme günlükleri | `<target>/Documents-Backup/<Device>/_backup_logs/backup_YYYYMMDD_HHMMSS.log` |
| Arşivler | `<target>/Documents-Backup/<Device>_<YYYYMMDD_HHMMSS>.zip\|tar.gz` |
| Yerel geçici yedekleme | `~/.local_backup_temp` |
| Windows izleyici görevi | Zamanlanmış Görev `SmartBackupWatcher` |
| macOS izleyici ajanı | `~/Library/LaunchAgents/com.smartbackup.watcher.plist` |
| Linux izleyici birimi | `~/.config/systemd/user/smartbackup-watcher.service` |

### D. Ek kaynaklar

- [`README.tr.md`](README.tr.md) — genel bakış ve hızlı başlangıç (Türkçe)
- [`docs/CONTRIBUTING.md`](../CONTRIBUTING.md) — geliştirme kurulumu, testler, linter (İngilizce)
- [`docs/CHANGELOG.md`](../CHANGELOG.md) — sürüm geçmişi (İngilizce)
