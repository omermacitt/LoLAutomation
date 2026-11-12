fn main() {
    println!("cargo:rerun-if-env-changed=RUNEPILOT_UPDATE_PUBLIC_KEY");
    if std::env::var("CARGO_CFG_TARGET_OS").as_deref() == Ok("windows") {
        // Integration tests that instantiate Tauri's mock runtime also link
        // Common Controls v6. Bare cargo test binaries have no app manifest.
        let manifest =
            std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("windows/test.manifest.xml");
        println!("cargo:rerun-if-changed={}", manifest.display());
        println!("cargo:rustc-link-arg-tests=/MANIFEST:EMBED");
        println!(
            "cargo:rustc-link-arg-tests=/MANIFESTINPUT:{}",
            manifest.display()
        );
    }
    tauri_build::build()
}
