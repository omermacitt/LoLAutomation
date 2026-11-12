use std::io::{Read, Write};
use std::net::TcpListener;
use std::time::Duration;
use tauri_plugin_updater::UpdaterExt;

fn verifies_fixture(bytes: Vec<u8>, version: &str, download_status: u16) -> bool {
    verifies_package(
        bytes,
        version,
        download_status,
        include_str!("../test-fixtures/public-key.txt"),
        include_str!("../test-fixtures/update.bin.sig"),
    )
}

fn verifies_package(
    bytes: Vec<u8>,
    version: &str,
    download_status: u16,
    public_key: &str,
    signature: &str,
) -> bool {
    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    let port = listener.local_addr().unwrap().port();
    let manifest = serde_json::json!({
        "version": version,
        "platforms": { "windows-x86_64": {
            "url": format!("http://127.0.0.1:{port}/package"),
            "signature": signature.trim(),
        }}
    })
    .to_string();
    let server = std::thread::spawn(move || {
        for (status, body) in [(200, manifest.into_bytes()), (download_status, bytes)] {
            let (mut socket, _) = listener.accept().unwrap();
            socket
                .set_read_timeout(Some(Duration::from_secs(3)))
                .unwrap();
            let mut request = [0; 4096];
            assert!(socket.read(&mut request).unwrap() > 0);
            write!(socket, "HTTP/1.1 {status} OK\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n", body.len()).unwrap();
            socket.write_all(&body).unwrap();
        }
    });
    // HTTP is enabled solely for this loopback fixture server. Production
    // endpoints are fixed HTTPS addresses; no test transport is compiled in.
    let mut context = tauri::test::mock_context(tauri::test::noop_assets());
    context.config_mut().plugins.0.insert(
        "updater".into(),
        serde_json::json!({
            "pubkey": public_key.trim(),
            "dangerousInsecureTransportProtocol": true,
            "requireSignedVersion": true,
        }),
    );
    let app = tauri::test::mock_builder()
        .plugin(tauri_plugin_updater::Builder::new().build())
        .build(context)
        .unwrap();
    let updater = app
        .updater_builder()
        .endpoints(vec![format!("http://127.0.0.1:{port}/manifest")
            .parse()
            .unwrap()])
        .unwrap()
        .target("windows-x86_64")
        .timeout(Duration::from_secs(30))
        .build()
        .unwrap();
    let update = tauri::async_runtime::block_on(updater.check())
        .unwrap()
        .unwrap();
    let result = tauri::async_runtime::block_on(update.download(|_, _| {}, || {}));
    server.join().unwrap();
    result.is_ok()
}

#[test]
fn authentic_package_passes_but_corruption_wrong_version_and_http_errors_are_rejected() {
    let bytes = include_bytes!("../test-fixtures/update.bin").to_vec();
    assert!(verifies_fixture(bytes.clone(), "1.0.1", 200));
    assert!(!verifies_fixture(
        b"corrupted package".to_vec(),
        "1.0.1",
        200
    ));
    assert!(!verifies_fixture(bytes.clone(), "1.0.2", 200));
    assert!(!verifies_fixture(bytes, "1.0.1", 500));
}

#[test]
#[ignore = "build_desktop -SignedUpdates supplies the actual package, key and version"]
fn verify_built_installer() {
    let path = std::env::var("RUNEPILOT_VERIFY_SETUP").expect("Setup path required");
    let version = std::env::var("RUNEPILOT_VERIFY_VERSION").expect("Version required");
    let public_key = std::env::var("RUNEPILOT_UPDATE_PUBLIC_KEY").expect("Public key required");
    let bytes = std::fs::read(&path).unwrap();
    let signature = std::fs::read_to_string(format!("{path}.sig")).unwrap();
    assert!(
        verifies_package(bytes, &version, 200, &public_key, &signature),
        "Setup signature does not match the application's public key and version"
    );
}
