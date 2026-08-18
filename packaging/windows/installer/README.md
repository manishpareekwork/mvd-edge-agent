# Windows Installer Foundation

The future target installer is:

```text
MVDInsightsEdgeAgent-Setup.exe
```

This step does not build an EXE/MSI installer and has not been field-tested on
a Windows industrial PC.

The scripted installation foundation is:

```powershell
.\scripts\install-service.ps1
```

Expected future bundle contents:

```text
mvd-edge-agent.exe
MVDInsightsEdgeAgent.exe
MVDInsightsEdgeAgent.xml
config\edge.env.example
scripts\install-service.ps1
scripts\uninstall-service.ps1
scripts\check-install.ps1
```

`MVDInsightsEdgeAgent.exe` is the WinSW-style wrapper binary. It must be
selected, license-reviewed, checksum-verified, and signed/provenanced before
distribution.

The installer version must follow the Edge Agent package version from
`pyproject.toml`. Do not create an unrelated installer version stream unless a
future release process explicitly requires it.

Before broad external customer distribution, add:

- Windows code signing
- installer signing
- published SHA-256 checksums
- trusted MVD-hosted or GitHub Releases distribution
- rollback guidance
