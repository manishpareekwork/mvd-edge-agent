# Third-Party Windows Service Wrapper

MVD Insights Edge Agent uses a WinSW-style wrapper on Windows so the
PyInstaller-built `mvd-edge-agent.exe` can run as a Windows Service without a
Python installation on the field PC.

This repository does not download, commit, or redistribute a WinSW executable.
The exact WinSW dependency version is still pending release selection.

Before a customer-distributable Windows bundle is created, the release process
must document:

- selected WinSW project and version
- license review approval
- trusted download source
- SHA-256 checksum
- signature or provenance verification, where available
- location of the reviewed wrapper binary in the release bundle

The current Windows service scripts expect the reviewed wrapper binary at:

```text
packaging/windows/service/MVDInsightsEdgeAgent.exe
```

The wrapper executable must sit next to:

```text
MVDInsightsEdgeAgent.xml
mvd-edge-agent.exe
```

Do not rename or bundle an unverified executable as
`MVDInsightsEdgeAgent.exe`.
