use crate::policy;
use base64::{engine::general_purpose::STANDARD, Engine};
use reqwest::{redirect::Policy, Client};
use serde::{Deserialize, Serialize};
use std::{
    collections::HashMap,
    io::{BufRead, BufReader, Read, Write},
    path::PathBuf,
    process::{Child, ChildStdin, Command, Stdio},
    sync::{mpsc, Arc, Mutex},
    time::{Duration, Instant},
};

pub const VERSION: &str = env!("CARGO_PKG_VERSION");
pub const PROTOCOL: u32 = 1;
const MAX_RESPONSE: usize = 4 * 1024 * 1024;

#[derive(Clone, Serialize)]
pub struct Status {
    pub phase: String,
    pub generation: u64,
    pub version: &'static str,
    pub error: Option<String>,
}

#[derive(Deserialize)]
struct Ready {
    event: String,
    protocol: u32,
    version: String,
    port: u16,
}

struct OwnedChild {
    child: Child,
    stdin: ChildStdin,
    #[cfg(windows)]
    _job: Job,
}

#[cfg(windows)]
struct Job(windows_sys::Win32::Foundation::HANDLE);
#[cfg(windows)]
unsafe impl Send for Job {}
#[cfg(windows)]
impl Job {
    fn attach(child: &Child) -> Result<Self, String> {
        use std::{mem::size_of, os::windows::io::AsRawHandle};
        use windows_sys::Win32::{Foundation::CloseHandle, System::JobObjects::*};
        unsafe {
            let handle = CreateJobObjectW(std::ptr::null(), std::ptr::null());
            if handle.is_null() {
                return Err("Windows süreç koruması başlatılamadı.".into());
            }
            let mut info: JOBOBJECT_EXTENDED_LIMIT_INFORMATION = std::mem::zeroed();
            info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
            if SetInformationJobObject(
                handle,
                JobObjectExtendedLimitInformation,
                &info as *const _ as _,
                size_of::<JOBOBJECT_EXTENDED_LIMIT_INFORMATION>() as u32,
            ) == 0
                || AssignProcessToJobObject(handle, child.as_raw_handle() as _) == 0
            {
                CloseHandle(handle);
                return Err("Windows süreç koruması başlatılamadı.".into());
            }
            Ok(Self(handle))
        }
    }
}
#[cfg(windows)]
impl Drop for Job {
    fn drop(&mut self) {
        unsafe {
            windows_sys::Win32::Foundation::CloseHandle(self.0);
        }
    }
}

pub struct Backend {
    pub status: Status,
    child: Option<OwnedChild>,
    port: Option<u16>,
    token: String,
    client: Client,
}

pub type SharedBackend = Arc<Mutex<Backend>>;

impl Backend {
    pub fn new() -> SharedBackend {
        Arc::new(Mutex::new(Self {
            status: Status {
                phase: "starting".into(),
                generation: 1,
                version: VERSION,
                error: None,
            },
            child: None,
            port: None,
            token: String::new(),
            client: Client::builder()
                .no_proxy()
                .redirect(Policy::none())
                .connect_timeout(Duration::from_secs(2))
                .timeout(Duration::from_secs(20))
                .build()
                .unwrap(),
        }))
    }

    pub fn current(&mut self) -> Status {
        if self.status.phase == "ready" {
            if let Some(child) = &mut self.child {
                if !matches!(child.child.try_wait(), Ok(None)) {
                    self.status.phase = "failed".into();
                    self.status.error = Some(
                        "Servis bağlantısı kesildi. Yeniden bağlanarak devam edebilirsin.".into(),
                    );
                    self.port = None;
                }
            }
        }
        self.status.clone()
    }
}

fn executable() -> Result<PathBuf, String> {
    let parent = std::env::current_exe().map_err(|_| "Uygulama yolu okunamadı.")?;
    let sibling = parent.parent().unwrap().join("runepilot-backend.exe");
    if sibling.is_file() {
        return Ok(sibling);
    }
    if cfg!(debug_assertions) {
        let source = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("binaries/runepilot-backend-x86_64-pc-windows-msvc.exe");
        if source.is_file() {
            return Ok(source);
        }
    }
    Err("RunePilot servis dosyası bulunamadı. Uygulamayı yeniden kur.".into())
}

pub fn start(shared: SharedBackend) {
    let generation = shared.lock().unwrap().status.generation;
    let result = spawn(&shared, generation);
    if let Err(message) = result {
        let mut state = shared.lock().unwrap();
        if state.status.generation == generation && state.status.phase != "stopping" {
            state.status.phase = "failed".into();
            state.status.error = Some(message);
            state.port = None;
            if let Some(mut child) = state.child.take() {
                let _ = child.child.kill();
                let _ = child.child.wait();
            }
        }
    }
}

fn spawn(shared: &SharedBackend, generation: u64) -> Result<(), String> {
    let token = format!(
        "{}{}",
        uuid::Uuid::new_v4().simple(),
        uuid::Uuid::new_v4().simple()
    );
    let mut command = Command::new(executable()?);
    command
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .env("PYTHONUTF8", "1")
        .env("RUNEPILOT_DISABLE_AUTO_UPDATE", "1");
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        command.creation_flags(0x08000000); // CREATE_NO_WINDOW; stdio pipes stay usable.
    }
    let mut child = command
        .spawn()
        .map_err(|_| "RunePilot servisi başlatılamadı. Kurulumu kontrol et.".to_string())?;
    #[cfg(windows)]
    let job = match Job::attach(&child) {
        Ok(job) => job,
        Err(error) => {
            let _ = child.kill();
            let _ = child.wait();
            return Err(error);
        }
    };
    let mut stdin = child.stdin.take().unwrap();
    let stdout = child.stdout.take().unwrap();
    let stderr = child.stderr.take().unwrap();
    std::thread::spawn(move || {
        let _ = std::io::copy(&mut BufReader::new(stderr), &mut std::io::sink());
    });
    let profile = std::env::var("RUNEPILOT_PROFILE_DIR").ok();
    let bootstrap = serde_json::json!({"token":token,"profile_dir":profile});
    if writeln!(stdin, "{bootstrap}").is_err() {
        let _ = child.kill();
        let _ = child.wait();
        return Err("Servis bağlantısı kurulamadı.".into());
    }
    {
        let mut state = shared.lock().unwrap();
        if state.status.generation != generation || state.status.phase != "starting" {
            let _ = child.kill();
            let _ = child.wait();
            return Err("Başlangıç iptal edildi.".into());
        }
        state.child = Some(OwnedChild {
            child,
            stdin,
            #[cfg(windows)]
            _job: job,
        });
        state.token = token;
    }
    let (send, receive) = mpsc::channel();
    std::thread::spawn(move || {
        let mut line = String::new();
        let result = BufReader::new(stdout.take(8193)).read_line(&mut line);
        let _ = send.send(if result.is_ok() && line.len() <= 8192 {
            serde_json::from_str::<Ready>(&line).ok()
        } else {
            None
        });
    });
    let ready = receive.recv_timeout(Duration::from_secs(55)).ok().flatten().ok_or("RunePilot servisi hazır olmadı. Yeniden dene; devam ederse kurulum ve profil erişimini kontrol et.")?;
    if ready.event != "ready"
        || ready.protocol != PROTOCOL
        || ready.version != VERSION
        || ready.port == 0
    {
        return Err("Kurulum dosyalarının sürümleri eşleşmiyor. Uygulamayı yeniden kur.".into());
    }
    let mut state = shared.lock().unwrap();
    if state.status.generation != generation || state.status.phase != "starting" {
        return Err("Başlangıç iptal edildi.".into());
    }
    state.port = Some(ready.port);
    state.status.phase = "ready".into();
    state.status.error = None;
    Ok(())
}

pub fn stop(shared: &SharedBackend) {
    let child = {
        let mut state = shared.lock().unwrap();
        state.status.phase = "stopping".into();
        state.port = None;
        state.token.clear();
        state.child.take()
    };
    shutdown_child(child);
}

fn shutdown_child(child: Option<OwnedChild>) {
    if let Some(mut owned) = child {
        let _ = writeln!(owned.stdin, "{{\"command\":\"shutdown\"}}");
        let deadline = Instant::now() + Duration::from_secs(15);
        while Instant::now() < deadline {
            if !matches!(owned.child.try_wait(), Ok(None)) {
                return;
            }
            std::thread::sleep(Duration::from_millis(50));
        }
        let _ = owned.child.kill();
        let _ = owned.child.wait();
    }
}

pub fn restart(shared: SharedBackend) -> Result<(), String> {
    let child = {
        let mut state = shared.lock().unwrap();
        if state.current().phase != "failed" {
            return Err("Mevcut bağlantının sonucu bekleniyor.".into());
        }
        state.status.generation += 1;
        state.status.phase = "starting".into();
        state.status.error = None;
        state.port = None;
        state.token.clear();
        state.child.take()
    };
    std::thread::spawn(move || {
        shutdown_child(child);
        start(shared);
    });
    Ok(())
}

#[derive(Deserialize)]
pub struct ApiRequest {
    pub method: String,
    pub path: String,
    pub body: Option<String>,
    pub if_match: Option<String>,
    pub generation: u64,
}

#[derive(Serialize)]
pub struct ApiResponse {
    pub status: u16,
    pub headers: HashMap<String, String>,
    pub body: String,
}

pub async fn request(
    shared: &SharedBackend,
    input: ApiRequest,
    image_only: bool,
) -> Result<(u16, HashMap<String, String>, Vec<u8>), String> {
    if !policy::allowed(&input.method, &input.path, image_only)
        || input
            .body
            .as_ref()
            .is_some_and(|body| body.len() > 1024 * 1024)
    {
        return Err("Bu uygulama isteğine izin verilmiyor.".into());
    }
    let (client, port, token) = {
        let mut state = shared.lock().unwrap();
        if state.current().phase != "ready" || state.status.generation != input.generation {
            return Err("Servis bağlantısı değişti. Sonucu kontrol edip yeniden dene.".into());
        }
        (
            state.client.clone(),
            state.port.unwrap(),
            state.token.clone(),
        )
    };
    let method =
        reqwest::Method::from_bytes(input.method.as_bytes()).map_err(|_| "Geçersiz istek.")?;
    let mut query = client
        .request(method, format!("http://127.0.0.1:{port}{}", input.path))
        .header("X-RunePilot-Desktop", token);
    if let Some(body) = input.body {
        query = query.header("Content-Type", "application/json").body(body);
    }
    if let Some(revision) = input.if_match {
        query = query.header("If-Match", revision);
    }
    let mut response = query
        .send()
        .await
        .map_err(|_| "Servise ulaşılamadı. İşlem sonucu doğrulanamadı.")?;
    if response
        .content_length()
        .is_some_and(|size| size > MAX_RESPONSE as u64)
    {
        return Err("Servis yanıtı çok büyük.".into());
    }
    let status = response.status().as_u16();
    let headers = ["content-type", "etag", "cache-control"]
        .iter()
        .filter_map(|name| {
            response
                .headers()
                .get(*name)
                .and_then(|value| value.to_str().ok())
                .map(|value| (name.to_string(), value.to_string()))
        })
        .collect();
    let mut bytes = Vec::new();
    while let Some(chunk) = response
        .chunk()
        .await
        .map_err(|_| "Servis yanıtı tamamlanamadı.")?
    {
        if bytes.len() + chunk.len() > MAX_RESPONSE {
            return Err("Servis yanıtı çok büyük.".into());
        }
        bytes.extend_from_slice(&chunk);
    }
    if shared.lock().unwrap().status.generation != input.generation {
        return Err("Eski servis yanıtı yok sayıldı. Sonucu yeniden kontrol et.".into());
    }
    Ok((status, headers, bytes))
}

pub async fn json_request(
    shared: &SharedBackend,
    input: ApiRequest,
) -> Result<ApiResponse, String> {
    let (status, headers, bytes) = request(shared, input, false).await?;
    Ok(ApiResponse {
        status,
        headers,
        body: STANDARD.encode(bytes),
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::net::TcpListener;

    #[test]
    fn image_bridge_keeps_bytes_and_never_follows_redirects() {
        for (status, body) in [(200, b"PNG-data".as_slice()), (302, b"".as_slice())] {
            let listener = TcpListener::bind("127.0.0.1:0").unwrap();
            let port = listener.local_addr().unwrap().port();
            let server = std::thread::spawn(move || {
                let (mut socket, _) = listener.accept().unwrap();
                socket
                    .set_read_timeout(Some(Duration::from_secs(3)))
                    .unwrap();
                let mut bytes = [0; 8192];
                let size = socket.read(&mut bytes).unwrap();
                let request = String::from_utf8_lossy(&bytes[..size]).to_lowercase();
                assert!(request.starts_with("get /runes/icons/8005 http/1.1"));
                assert!(request.contains("x-runepilot-desktop: test-private-key"));
                write!(socket, "HTTP/1.1 {status} OK\r\nContent-Type: image/png\r\nContent-Length: {}\r\nLocation: http://127.0.0.1:1/forbidden\r\nConnection: close\r\n\r\n", body.len()).unwrap();
                socket.write_all(body).unwrap();
            });
            let shared = Backend::new();
            {
                let mut state = shared.lock().unwrap();
                state.status.phase = "ready".into();
                state.port = Some(port);
                state.token = "test-private-key".into();
            }
            let input = ApiRequest {
                method: "GET".into(),
                path: "/runes/icons/8005".into(),
                body: None,
                if_match: None,
                generation: 1,
            };
            let result = tauri::async_runtime::block_on(request(&shared, input, true)).unwrap();
            assert_eq!(result.0, status);
            assert_eq!(result.2, body);
            assert!(!result.1.contains_key("location"));
            server.join().unwrap();
        }
    }

    #[test]
    fn stale_session_and_retired_routes_fail_before_network_access() {
        let shared = Backend::new();
        for (path, generation) in [("/settings", 999), ("/accounts", 1)] {
            let input = ApiRequest {
                method: "GET".into(),
                path: path.into(),
                body: None,
                if_match: None,
                generation,
            };
            assert!(tauri::async_runtime::block_on(json_request(&shared, input)).is_err());
        }
    }
}
