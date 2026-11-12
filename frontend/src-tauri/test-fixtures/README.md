Only a public test key, a non-executable text payload and its version-bound
signature are stored here. The private fixture key is not shipped or committed.
Tests download from a loopback server, verify with the real Tauri updater, and
never install the payload or call the production release endpoint.
