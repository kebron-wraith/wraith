# WRAITH — AI Security Organism

> Forward-deployed Autonomous Knowledge Architecture

WRAITH is a self-evolving, distributed AI security platform. Each device runs a **WRAITH Cell** — 28 autonomous security agents that scan, detect, learn, and share intelligence via P2P mesh networking.

## Repositories

| Repository | Description | Access |
|---|---|---|
| [wraith-admin](https://github.com/kebron-wraith/wraith-admin) | Cell code, Admin brain, Tracker server, Tests | Public |
| wraith (this repo) | Public showcase — README, LICENSE | Public |

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    WRAITH ADMIN                          │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │  Research    │  │  Tracker     │  │  Dashboard    │  │
│  │  Engine      │  │  Server      │  │  (Web UI)     │  │
│  └─────────────┘  └──────────────┘  └───────────────┘  │
│         │                │                  │            │
│         └────────────────┼──────────────────┘            │
│                          │                               │
│              Admin-Cell Protocol (HMAC-signed)           │
│                          │                               │
└──────────────────────────┼───────────────────────────────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
    ┌────▼────┐      ┌────▼────┐      ┌────▼────┐
    │ Cell A  │◄────►│ Cell B  │◄────►│ Cell C  │
    │ 28      │ P2P  │ 28      │ P2P  │ 28      │
    │ agents  │ mesh │ agents  │ mesh │ agents  │
    └─────────┘      └─────────┘      └─────────┘
```

## Cell Agents (28)

| Category | Agents |
|---|---|
| **Network** | NetworkScanner, PortScanner, VulnerabilityScanner, IntrusionDetector, FirewallMonitor, DNSMonitor, SSLMonitor, HTTPMonitor |
| **Malware** | MalwareDetector, RansomwareDetector, RootkitDetector, KeyloggerDetector |
| **Social** | PhishingDetector, SocialEngineeringDetector |
| **Infrastructure** | CloudSecurityAgent, IoTAgent, MobileAgent, ContainerAgent |
| **AI Security** | AIAgentDetector, PromptInjectionDetector, DeepfakeDetector |
| **Operations** | PasswordAuditor, PatchManager, BackupMonitor, LogAnalyzer, ThreatIntelligence, SelfEvolver, HoneyPot |

## Quick Start

```bash
# Clone
git clone https://github.com/kebron-wraith/wraith-admin.git
cd wraith-admin

# Install
pip install pyyaml requests pytest

# Run tests
python -m pytest test_wraith.py -v --timeout=20

# Start a cell
python cell_core.py --scan

# Start tracker server
python tracker_server.py

# Start admin
python admin_system.py cycle
```

## One-Line Install (Coming Soon)

```bash
curl -fsSL https://wraith.one/install | bash
```

## License

MIT License — See [LICENSE](LICENSE) for details.

---

🦅 WRAITH — The organism cannot die if it's everywhere at once.
