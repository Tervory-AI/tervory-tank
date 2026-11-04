# Tervory desktop window

The window reuses Microsoft Code-OSS (MIT), pinned by release **and commit** in
`upstream.json`. Only build scripts, product patches, the built-in extension and
license notices are tracked here; the upstream source stays in `.tmp/code-oss`.

Use the Node version in `upstream.json`. Run `npm ci --prefix window`, then
`npm --prefix window run prepare-source` and `npm --prefix window run build`.
Build on the target OS/CPU: Windows x64/arm64, macOS x64/arm64, Linux x64/arm64.
Code-OSS requires its native build prerequisites (C++ toolchain, Python; GTK,
X11, libsecret and Kerberos development libraries on Linux). Build output is an
unsigned portable archive in `window/dist`, with SHA256SUMS and build metadata.
Check the checksum before extracting; launch Tervory.exe, Tervory.app, or bin/tervory.

`window-v<window/package.json version>` tags build all six distributions in CI.
No release tag is created by these scripts. Until founder signing accounts are
configured, distributions are explicitly unsigned; no notarization or
Authenticode claim is made. Code-OSS third-party notices remain in each build.

The exact supplied `workspace/public/brand/tervory-logo.png` is copied for PNG
assets and converted to ICO/ICNS for native icons. No logo is redrawn. Open VSX
supplies extensions. The product disables Microsoft telemetry/crash reporting
and removes the default Copilot provider. Every Tervory model request uses Tank.
