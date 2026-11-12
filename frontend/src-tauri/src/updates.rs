//! Only compiled-in release endpoints and verified, complete installers are accepted.
use serde::Serialize;
use std::sync::{
    atomic::{AtomicBool, Ordering},
    Mutex,
};
use std::time::Duration;
use tauri::{AppHandle, Emitter};
use tauri_plugin_updater::{Update, UpdaterExt};

const REPO: &str = "omermacitt/LoLAutomation";
const PUBLIC_KEY: &str = match option_env!("RUNEPILOT_UPDATE_PUBLIC_KEY") {
    Some(value) => value,
    None => "",
};

#[derive(Default)]
pub struct Updates {
    data: Mutex<Data>,
    pub installing: AtomicBool,
}

#[derive(Default)]
struct Data {
    busy: bool,
    offer: Option<Update>,
    bytes: Option<Vec<u8>>,
}

#[derive(Serialize)]
pub struct Offer {
    pub version: String,
    pub current_version: String,
    pub notes: String,
}

#[derive(Serialize)]
pub struct Check {
    pub enabled: bool,
    pub channel: &'static str,
    pub update: Option<Offer>,
}

#[derive(Clone, Serialize)]
struct Progress {
    downloaded: u64,
    total: Option<u64>,
}

pub fn channel(version: &str) -> &'static str {
    if version.contains('-') {
        "beta"
    } else {
        "stable"
    }
}

fn endpoint(version: &str) -> String {
    if channel(version) == "beta" {
        format!("https://github.com/{REPO}/releases/download/update-beta/latest.json")
    } else {
        format!("https://github.com/{REPO}/releases/latest/download/latest.json")
    }
}

fn valid_download(update: &Update) -> bool {
    update.download_url.scheme() == "https"
        && update.download_url.host_str() == Some("github.com")
        && update.download_url.port().is_none()
        && update.download_url.username().is_empty()
        && update.download_url.password().is_none()
        && update.download_url.query().is_none()
        && update.download_url.fragment().is_none()
        && update
            .download_url
            .path()
            .starts_with(&format!("/{REPO}/releases/download/v{}/", update.version))
        && update.download_url.path().ends_with("-x64.exe")
}

impl Updates {
    fn begin(&self) -> Result<(), String> {
        let mut state = self.data.lock().unwrap();
        if state.busy || self.installing.load(Ordering::SeqCst) {
            return Err("Bir güncelleme işlemi zaten sürüyor.".into());
        }
        state.busy = true;
        Ok(())
    }

    pub async fn check(&self, app: &AppHandle) -> Result<Check, String> {
        self.begin()?;
        let version = app.package_info().version.to_string();
        let result = async {
            if PUBLIC_KEY.trim().is_empty() {
                return Ok(Check {
                    enabled: false,
                    channel: channel(&version),
                    update: None,
                });
            }
            let offer = app
                .updater_builder()
                .pubkey(PUBLIC_KEY.trim())
                .endpoints(vec![endpoint(&version).parse().unwrap()])
                .map_err(|_| "Güncelleme adresi hazırlanamadı.")?
                .timeout(Duration::from_secs(15))
                .build()
                .map_err(|_| "Güncelleme ayarları okunamadı.")?
                .check()
                .await
                .map_err(|_| {
                    "Güncellemeler kontrol edilemedi. İnternet bağlantını kontrol edip tekrar dene."
                })?;
            if offer.as_ref().is_some_and(|update| {
                !valid_download(update)
                    || (channel(&version) == "stable" && channel(&update.version) != "stable")
            }) {
                return Err("Bu kanala uygun bir güncelleme paketi bulunamadı.".into());
            }
            let update = offer.as_ref().map(|value| Offer {
                version: value.version.clone(),
                current_version: value.current_version.clone(),
                notes: value.body.clone().unwrap_or_default(),
            });
            let mut state = self.data.lock().unwrap();
            state.offer = offer;
            state.bytes = None;
            Ok(Check {
                enabled: true,
                channel: channel(&version),
                update,
            })
        }
        .await;
        self.data.lock().unwrap().busy = false;
        result
    }

    pub async fn download(&self, app: &AppHandle) -> Result<(), String> {
        self.begin()?;
        let offer = self.data.lock().unwrap().offer.clone();
        let result = async {
            let mut offer = offer.ok_or("Önce güncellemeleri kontrol et.")?;
            offer.timeout = Some(Duration::from_secs(300));
            let mut downloaded = 0;
            let bytes = offer.download(|chunk, total| {
                downloaded += chunk as u64;
                let _ = app.emit("desktop-update-progress", Progress { downloaded, total });
            }, || {}).await.map_err(|_| "Güncelleme indirilemedi veya imzası doğrulanamadı. Mevcut sürümü kullanabilir, tekrar deneyebilirsin.")?;
            self.data.lock().unwrap().bytes = Some(bytes);
            Ok(())
        }.await;
        self.data.lock().unwrap().busy = false;
        result
    }

    pub fn take_install(&self) -> Result<(Update, Vec<u8>), String> {
        self.begin()?;
        let mut state = self.data.lock().unwrap();
        let result = match (state.offer.clone(), state.bytes.take()) {
            (Some(offer), Some(bytes)) => offer
                .verify(&bytes)
                .map(|_| (offer, bytes))
                .map_err(|_| "Güncelleme paketi doğrulanamadı. Tekrar indir.".to_string()),
            _ => Err("Önce güncellemeyi indir.".into()),
        };
        state.busy = false;
        if result.is_ok() {
            self.installing.store(true, Ordering::SeqCst);
        }
        result
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn stable_and_beta_have_separate_fixed_endpoints() {
        assert!(endpoint("1.0.0").ends_with("/releases/latest/download/latest.json"));
        assert!(endpoint("1.0.1-beta.2").ends_with("/releases/download/update-beta/latest.json"));
    }
    #[test]
    fn missing_download_and_parallel_operations_cannot_install() {
        let updates = Updates::default();
        assert!(updates.take_install().is_err());
        assert!(!updates.installing.load(Ordering::SeqCst));
        updates.begin().unwrap();
        assert!(updates.begin().is_err());
        assert!(updates.take_install().is_err());
    }
}
