# Multi-Protocol Sync Monitor for Windows

A Python-based network monitoring tool for capturing and analyzing synchronization protocols used in professional AV and digital signage systems.

## Supported Protocols

### PTP (Precision Time Protocol) - IEEE 1588-2019
- Monitors multicast group `224.0.1.129` on ports 319 (event) and 320 (general)
- Captures all PTP message types: Sync, Delay_Req, Announce, Follow_Up, etc.
- Displays clock identity, domain, sequence numbers, and correction fields

### BrightSign Sync Protocol
- Monitors UDP traffic on port 5000 (configurable)
- Parses text-based synchronization commands:
  - `pre-{event}` - Preload content for synchronized playback
  - `ply-{event}` - Play preloaded synchronized content
  - Custom UDP event commands

## Requirements

- Python 3.7+
- Windows OS (uses `WindowsSelectorEventLoopPolicy`)
- Administrator/elevated privileges (for multicast socket binding)

## Installation

1. Clone or download this repository
2. No additional dependencies required (uses Python standard library)

Optional: For interface selection by name, install `netifaces`:
```bash
pip install netifaces
```

## Usage

### Basic Usage

Monitor both PTP and BrightSign protocols on all interfaces:
```bash
python ptpcheck.py
```

### Command Line Options

```bash
python ptpcheck.py [OPTIONS]
```

**Options:**

- `-i, --interface <name|ip>` - Network interface name or IP address (default: all interfaces)
- `-g, --group <ip>` - PTP multicast group address (default: 224.0.1.129)
- `-b, --brightsign-port <port>` - BrightSign UDP port (default: 5000)
- `-o, --output <file>` - Log output to file
- `--no-ptp` - Disable PTP monitoring
- `--no-brightsign` - Disable BrightSign monitoring

### Examples

Monitor only PTP traffic:
```bash
python ptpcheck.py --no-brightsign
```

Monitor only BrightSign on custom port:
```bash
python ptpcheck.py --no-ptp -b 6000
```

Monitor on specific interface with file logging:
```bash
python ptpcheck.py -i 192.168.1.10 -o sync_log.txt
```

Monitor custom PTP multicast group:
```bash
python ptpcheck.py -g 224.0.1.130
```

## Output Format

### PTP Messages
```
[12:34:56.789] 192.168.1.100:319    | PTP Sync       | Domain: 0   | Seq: 1234  | Clock: ...a1b2c3d4
```

### BrightSign Messages
```
[12:34:56.789] 192.168.1.200:5000   | BrightSign SYNC_PRELOAD | Event: 'video1' | Full: 'pre-video1'
[12:34:57.123] 192.168.1.200:5000   | BrightSign SYNC_PLAY    | Event: 'video1' | Full: 'ply-video1'
[12:35:00.456] 192.168.1.201:5000   | BrightSign UDP_EVENT    | Command: 'pause'
```

### Statistics
Packet statistics are displayed every 100 packets:
```
Stats: Total: 400 | PTP: 285 | BrightSign: 115
```

Final statistics are shown when stopping the monitor (Ctrl+C).

## Use Cases

- **PTP Debugging**: Monitor PTP grandmaster/slave synchronization and identify clock drift issues
- **BrightSign Sync Testing**: Verify synchronized playback commands between BrightSign players
- **Network Diagnostics**: Troubleshoot timing and synchronization in AV installations
- **Protocol Analysis**: Capture and analyze multicast timing protocols

## Technical Details

### Architecture
- **Async I/O**: Uses Python's `asyncio` with `DatagramProtocol` for efficient packet handling
- **Multicast Support**: Properly joins IGMP multicast groups with `IP_ADD_MEMBERSHIP`
- **Non-blocking Sockets**: All sockets use non-blocking mode for concurrent monitoring
- **Dual Protocol**: Simultaneously monitors multiple UDP ports across different protocols

### PTP Packet Structure
Parses the 34-byte PTP header:
- Message type and version
- Domain number (for multiple PTP domains)
- Clock identity (EUI-64)
- Sequence ID (for message ordering)
- Correction field (for path delay compensation)

### BrightSign Protocol
Based on actual BrightSign player implementation:
- Plain text UDP messages (UTF-8 encoded)
- Synchronization prefixes: `pre-` and `ply-`
- Custom event/command strings for state machine control

## Troubleshooting

**No packets received:**
- Ensure you're running with administrator/elevated privileges
- Verify network interface is connected to the correct network
- Check Windows Firewall settings for UDP ports 319, 320, and 5000
- Confirm PTP devices are on the same network segment (multicast traffic doesn't route)

**"Permission denied" errors:**
- Run command prompt or PowerShell as Administrator
- Check that no other application is binding to the same ports

**BrightSign messages not appearing:**
- Verify BrightSign players are configured to send sync messages
- Check that the UDP port matches (default is 5000)
- Ensure players are on the same network

## File Logging

When using the `-o` option, messages are logged in CSV-like format:
```
2026-05-14T12:34:56.789,192.168.1.100,319,[timestamp] address | message details
```

The log file is appended to (not overwritten) and flushed after each write for real-time analysis.

## License

This tool is provided as-is for network monitoring and diagnostics purposes.

## Contributing

Contributions welcome! Areas for enhancement:
- Support for PTP over Ethernet (Layer 2)
- PTPv1 (IEEE 1588-2002) support
- Additional digital signage protocols
- Enhanced statistics and analysis features
- Cross-platform support (Linux, macOS)
