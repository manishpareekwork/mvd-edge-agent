# USB Distribution Template

Future field USB bundle shape:

```text
MVD-Edge-Agent/
├── WINDOWS-X64/
│   ├── installer/
│   ├── executable/
│   └── service/
├── LINUX-X64/
│   ├── install.sh
│   └── mvd-edge-agent
├── LINUX-ARM64/
│   ├── install.sh
│   └── mvd-edge-agent
├── CONFIG/
│   └── edge.env.example
├── DRIVERS/
│   └── README.md
├── DOCS/
│   └── QUICK_START.md
└── checksums.txt
```

This directory is a template only. It intentionally contains no generated
executables, service wrapper binaries, proprietary drivers, or fake checksums.

The bundle version should follow the Edge Agent package version from
`pyproject.toml`.

Before external customer distribution, release artifacts require SHA-256
checksums, signing decisions, and trusted MVD distribution.
