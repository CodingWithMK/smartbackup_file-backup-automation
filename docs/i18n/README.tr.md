<!-- Source: README.md | Version: 0.9.0 | Language: tr (Türkçe) | Synced: 2026-11-25 -->

<div align="center">

# 🔄 SmartBackup

**Geliştiriciler için Akıllı Yedekleme Sistemi**

`node_modules`, sanal ortamlar (virtual environments) ve diğer derleme çıktılarını otomatik olarak atlayarak önemli dosyalarınızı yedekleyin.

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![CI](https://github.com/CodingWithMK/smartbackup_file-backup-automation/actions/workflows/ci.yml/badge.svg)](https://github.com/CodingWithMK/smartbackup_file-backup-automation/actions)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)](/)

🌐 [English](../../README.md) · **Türkçe** · [Deutsch](README.de.md)

[Özellikler](#-özellikler) •
[Hızlı Başlangıç](#-hızlı-başlangıç) •
[📖 Kullanıcı Kılavuzu (İngilizce)](../USER_GUIDE.md) •
[Katkıda Bulunma](#-katkıda-bulunma)

</div>

---

> # 📖 **Tam dokümantasyon: [SmartBackup Kullanıcı Kılavuzu (İngilizce)](../USER_GUIDE.md)**
> Kurulum (`pip` / `uv` / geliştirme ortamı), **tüm CLI komutları ve parametreleri**, artımlı manifest
> yönetimi, otomatik sürücü izleyici ve arka plan servisi, geri yükleme ve kurtarma, yapılandırma ve
> platformlar arası sorun giderme — hepsi tek bir yerde.

---

## 🤔 Neden SmartBackup?

Belgeler (`Documents`) klasörünüzü yedeklemeye çalışırken devasa `node_modules` klasörleri veya
Python sanal ortamları yüzünden saatlerce beklediğiniz oldu mu?

**SmartBackup bu sorunu çözer.** Geliştirme çıktılarını otomatik olarak algılar ve atlar; böylece
yedeklemeleriniz:

- ⚡ **10 kat daha hızlı** — gigabaytlarca bağımlılık klasörünü atlayın
- 💾 **10 kat daha küçük** — yalnızca gerçekten önemli olan dosyaları yedekleyin
- 🧠 **Akıllı** — manifest tabanlı artımlı yedekleme ile sadece değişen dosyaları kopyalayın
- 💻 **Çoklu cihaz uyumlu** — birden fazla bilgisayar aynı harici diski güvenle paylaşır (cihaz adına göre alt klasörler)
- 🔌 **Sıfır yapılandırma** — Windows, macOS ve Linux üzerinde kutudan çıktığı gibi çalışır

---

## ✨ Özellikler

| Özellik | Açıklama |
|---------|----------|
| 🚀 **Platformlar Arası** | Windows, macOS ve Linux üzerinde sorunsuz çalışır |
| 🔍 **Akıllı Filtreleme** | `node_modules`, `venv`, `.git`, `__pycache__`, derleme çıktıları ve önbellekleri otomatik atlar |
| 📂 **Seçmeli Yedekleme** | Klavye onay kutularına sahip etkileşimli klasör seçici (`--select`), seçilmeyen klasör koruması ve denetim geçmişi |
| 📊 **Artımlı Yedekleme** | Otomatik algılamalı JSON veya SQLite manifest (`--manifest-format json\|sqlite`), özel SQLite `selective_backups` tablosu ve kesintisiz geçiş |
| 🔐 **SHA-256 Özetleme** | İsteğe bağlı kademeli doğrulama (`--hash` ≤ 50 MB, tüm dosyalar için `--hash-all`) |
| 🔄 **Geri Yükleme Desteği** | Çakışma stratejileri (`skip`, `overwrite`, `newer`, `rename`), kalıp filtreleme, `--manifest-info`, simülasyon önizlemesi |
| 💻 **Çoklu Cihaz** | Cihaz başına ayrı yedek klasörü — birden fazla makine tek bir diski güvenle paylaşır |
| 📦 **Sıkıştırma** | `zip` / `tar.gz` — yedekleme sırasında veya sonrasında `compress` komutuyla |
| 🔌 **Otomatik Algılama** | Harici sürücüleri otomatik bulur; isteğe bağlı izleyici servisi disk takıldığında onay ister |
| ⚙️ **Yapılandırma CLI'ı** | Kalıcı ayarları ve hariç tutma kurallarını `smartbackup config` ile yönetin (elle JSON düzenlemeye gerek yok) |
| 🔔 **Masaüstü Bildirimleri** | Tamamlanma bildirimleri (`--notify`): `osascript`, `notify-send` veya PowerShell üzerinden isteğe bağlı uyarılar |
| 🗓️ **Zamanlama Yardımcısı** | `smartbackup schedule` ile işletim sistemine özel `schtasks`, `launchd`, `cron` ve `systemd` komutlarını yazdırın |
| 📝 **Ayrıntılı Günlükleme** | Kalıcı tek çubuklu Rich ilerleme göstergesi + yedekleme diskinde çalışma başına günlük dosyası |
| 🎯 **Minimal Bağımlılık** | Yalnızca `rich` + `typer` — geri kalan her şey Python standart kütüphanesi |

---

## 🚀 Hızlı Başlangıç

### Seçenek 1 — Tek Satırda Bağımsız Kurulum (Python Gerektirmez)

Temiz bir makinede doğrudan [GitHub Releases](https://github.com/CodingWithMK/smartbackup_file-backup-automation/releases) üzerinden önceden derlenmiş bağımsız çalıştırılabilir dosyayı kurun — Python, `pip` veya `uv` gerekmez:

**macOS & Linux (`curl`):**
```bash
curl -fsSL https://raw.githubusercontent.com/CodingWithMK/smartbackup_file-backup-automation/main/scripts/install.sh | sh
```

**Windows (PowerShell):**
```powershell
irm https://raw.githubusercontent.com/CodingWithMK/smartbackup_file-backup-automation/main/scripts/install.ps1 | iex
```

<details>
<summary>Belirli bir sürümü sabitleme</summary>

```bash
# macOS / Linux
SMARTBACKUP_VERSION=v0.9.0 curl -fsSL https://raw.githubusercontent.com/CodingWithMK/smartbackup_file-backup-automation/main/scripts/install.sh | sh
```

```powershell
# Windows (PowerShell)
$env:SMARTBACKUP_VERSION = "v0.9.0"; irm https://raw.githubusercontent.com/CodingWithMK/smartbackup_file-backup-automation/main/scripts/install.ps1 | iex
```

</details>

---

### Seçenek 2 — Kaynak Koddan / Python ile Çalıştırma (Geliştiriciler)

**Gereksinimler:** Python 3.9+ · Windows / macOS / Linux

#### Doğrudan çalıştırma (kurulum gerektirmez)

```bash
git clone https://github.com/CodingWithMK/smartbackup_file-backup-automation.git
cd smartbackup_file-backup-automation

python main.py            # Documents klasörünü otomatik algılanan harici sürücüye yedekler
```

#### pip ile kurulum

```bash
pip install .
smartbackup
```

#### uv ile kurulum (geliştiriciler için önerilen)

```bash
uv venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
uv pip install -e ".[dev]"
smartbackup
```

**Hepsi bu kadar!** Harici bir sürücü takın ve çalıştırın — SmartBackup sürücüyü otomatik bulur,
derleme çıktılarını atlar ve yalnızca son çalışmadan bu yana değişen dosyaları kopyalar. Hiçbir
sürücü bulunamazsa bunun yerine yerel geçici yedekleme seçeneği sunulur.

```bash
smartbackup --version     # doğrulama: smartbackup 0.9.0
smartbackup --help        # tüm komutlar ve seçenekler
```

---

## 💡 Sık Kullanılan Komutlar

```bash
smartbackup                                   # Documents klasörünü otomatik algılanan sürücüye yedekle
smartbackup --select                          # yedeklenecek üst düzey klasörleri etkileşimli olarak seç
smartbackup --select --dry-run                # klasörleri seç ve simüle et (hedefe sıfır yazma)
smartbackup --source ~/Projects               # özel bir klasörü yedekle
smartbackup --target /media/USB_DRIVE         # açıkça belirtilen bir hedef yola yedekle
smartbackup --dry-run                         # yedeklemeyi simüle et (kopyalama, manifest ve günlük yok)
smartbackup --manifest-format sqlite          # manifesti SQLite (.smartbackup_manifest.db) olarak sakla
smartbackup --notify                          # yedekleme tamamlandığında masaüstü bildirimi gönder
smartbackup --list-drives                     # kullanılabilir harici sürücüleri listele
smartbackup --hash                            # SHA-256 tabanlı değişiklik algılama (≤ 50 MB dosyalar)
smartbackup --target /media/USB --verify      # yedek bütünlüğünü manifeste göre doğrula
smartbackup --compress zip                    # yedekle ve ardından zip arşivi oluştur

smartbackup restore --source /media/USB_DRIVE --list                  # yedek içeriğini incele
smartbackup restore --source /media/USB_DRIVE --manifest-info         # manifest özetini göster
smartbackup restore --source /media/USB_DRIVE --conflict rename       # çakışmada her iki dosyayı da koru

smartbackup config list                       # kalıcı yapılandırmayı görüntüle
smartbackup config set manifest_format sqlite # varsayılan manifest biçimi olarak SQLite kaydet

smartbackup watch                             # ön planda harici sürücü izleyici
smartbackup daemon install                    # arka plan izleyici servisi (status/uninstall/clear-state)
smartbackup schedule --hours 24               # işletim sistemine özel zamanlanmış yedekleme komutlarını yazdır
```

Tüm açıklamalar, seçenekler ve kullanım senaryoları: **[Kullanıcı Kılavuzu (İngilizce) →](../USER_GUIDE.md)**

<details>
<summary><b>Varsayılan olarak neler hariç tutulur?</b></summary>

`node_modules`, `venv`/`.venv`/`.env`, `__pycache__`, `.git`/`.svn`/`.hg`, `dist`/`build`,
`target`, `bin`/`obj`, `.idea`/`.vscode`, `.next`/`.nuxt`, `.gradle`/`.m2`, önbellekler
(`.cache`, `.pytest_cache`, `.mypy_cache`, `.sass-cache`), geçici dosyalar (`*.tmp`, `*.log`,
`*.bak`, `~*`), ikili dosyalar (`*.pyc`, `*.exe`, `*.dll`, `*.so`, `*.dylib`, …), işletim sistemi
artıkları (`.DS_Store`, `Thumbs.db`, `desktop.ini`) — ayrıca yapısal olarak Python sanal ortamı
olduğu algılanan tüm dizinler.

Tam liste: [Kullanıcı Kılavuzu → Appendix B (İngilizce)](../USER_GUIDE.md#b-default-exclusions)

</details>

---

## 🤝 Katkıda Bulunma

Katkılarınız memnuniyetle karşılanır! Başlamak için:

1. Depoyu fork'layın
2. Yeni bir dal oluşturun: `git checkout -b feature/amazing-feature`
3. Değişikliklerinizi yapın
4. Testleri çalıştırın: `pytest` · Linter: `ruff check .`
5. Değişikliklerinizi commit edin: `git commit -m 'Add amazing feature'`
6. Dalınızı gönderin: `git push origin feature/amazing-feature`
7. Bir Pull Request açın

Ayrıntılar için [CONTRIBUTING.md (İngilizce)](../CONTRIBUTING.md) ve sürüm geçmişi için [CHANGELOG.md (İngilizce)](../CHANGELOG.md) dosyalarına göz atın.

---

## 📜 Lisans

Bu proje MIT Lisansı ile lisanslanmıştır — ayrıntılar için [LICENSE](../../LICENSE) dosyasına bakın.

---

## 🙏 Teşekkürler

- `node_modules` yedeklemekten yorulan geliştiriciler için ❤️ ile geliştirildi
- Yavaş yedeklemelerin verdiği bıkkınlıktan ilham alındı

---

<div align="center">

**Bu araç size zaman kazandırdıysa bir ⭐ bırakmayı düşünebilirsiniz**

[Hata Bildir](https://github.com/CodingWithMK/smartbackup_file-backup-automation/issues) •
[Özellik İste](https://github.com/CodingWithMK/smartbackup_file-backup-automation/issues)

</div>
