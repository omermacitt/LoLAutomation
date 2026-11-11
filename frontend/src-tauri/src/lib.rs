mod backend;
mod policy;

use backend::{ApiRequest, ApiResponse, SharedBackend, Status};
use std::sync::{
    atomic::{AtomicBool, Ordering},
    Arc,
};
use tauri::{Emitter, Manager};

struct Desktop {
    backend: SharedBackend,
    closing: Arc<AtomicBool>,
}

#[tauri::command]
fn desktop_status(state: tauri::State<'_, Desktop>) -> Status {
    state.backend.lock().unwrap().current()
}

#[tauri::command]
async fn desktop_request(
    state: tauri::State<'_, Desktop>,
    input: ApiRequest,
) -> Result<ApiResponse, String> {
    backend::json_request(&state.backend, input).await
}

#[tauri::command]
fn desktop_restart(state: tauri::State<'_, Desktop>) -> Result<(), String> {
    backend::restart(state.backend.clone())
}

#[tauri::command]
async fn desktop_close(
    app: tauri::AppHandle,
    state: tauri::State<'_, Desktop>,
) -> Result<(), String> {
    if state.closing.swap(true, Ordering::SeqCst) {
        return Ok(());
    }
    let backend = state.backend.clone();
    tauri::async_runtime::spawn_blocking(move || backend::stop(&backend))
        .await
        .map_err(|_| "Uygulama kapatılamadı.")?;
    if let Some(window) = app.get_webview_window("main") {
        window.destroy().map_err(|_| "Pencere kapatılamadı.")?;
    }
    app.exit(0);
    Ok(())
}

pub fn run() {
    let backend = backend::Backend::new();
    let cleanup = backend.clone();
    tauri::Builder::default()
        .plugin(
            tauri::plugin::Builder::<tauri::Wry>::new("local-navigation")
                .on_navigation(|_, url| {
                    (url.scheme() == "http"
                        && url.host_str() == Some("tauri.localhost")
                        && url.port().is_none())
                        || (cfg!(debug_assertions)
                            && url.scheme() == "http"
                            && url.host_str() == Some("127.0.0.1")
                            && url.port() == Some(5173))
                })
                .build(),
        )
        .plugin(tauri_plugin_single_instance::init(|app, _, _| {
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.unminimize();
                let _ = window.show();
                let _ = window.set_focus();
            }
        }))
        .manage(Desktop {
            backend: backend.clone(),
            closing: Arc::new(AtomicBool::new(false)),
        })
        .invoke_handler(tauri::generate_handler![
            desktop_status,
            desktop_request,
            desktop_restart,
            desktop_close
        ])
        .register_asynchronous_uri_scheme_protocol("runepilot", |context, request, responder| {
            if request.method() != tauri::http::Method::GET || request.uri().query().is_some() {
                responder.respond(
                    tauri::http::Response::builder()
                        .status(404)
                        .body(Vec::new())
                        .unwrap(),
                );
                return;
            }
            let backend = context.app_handle().state::<Desktop>().backend.clone();
            let path = request.uri().path().to_string();
            let generation = backend.lock().unwrap().status.generation;
            tauri::async_runtime::spawn(async move {
                let input = ApiRequest {
                    method: "GET".into(),
                    path,
                    body: None,
                    if_match: None,
                    generation,
                };
                let response = match backend::request(&backend, input, true).await {
                    Ok((status, headers, bytes)) => {
                        let mut response = tauri::http::Response::builder()
                            .status(status)
                            .header("Access-Control-Allow-Origin", "http://tauri.localhost")
                            .header("X-Content-Type-Options", "nosniff");
                        for (key, value) in headers {
                            response = response.header(key, value);
                        }
                        response.body(bytes).unwrap()
                    }
                    Err(_) => tauri::http::Response::builder()
                        .status(503)
                        .body(Vec::new())
                        .unwrap(),
                };
                responder.respond(response);
            });
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                let state = window.state::<Desktop>();
                if !state.closing.load(Ordering::SeqCst) {
                    api.prevent_close();
                    let _ = window.emit("desktop-close-requested", ());
                }
            }
        })
        .setup(move |_app| {
            std::thread::spawn(move || backend::start(backend));
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("RunePilot desktop initialization")
        .run(move |_app, event| {
            if let tauri::RunEvent::Exit = event {
                backend::stop(&cleanup);
            }
        });
}
