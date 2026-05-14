import asyncio
import socket
import struct
import datetime
import sys
import platform
import json
from typing import Optional, Tuple, List, Dict, Any
from enum import Enum

# --- PTP Constants ---
PTP_EVENT_PORT = 319      # Sync, Delay_Req, Pdelay_Req, Pdelay_Resp
PTP_GENERAL_PORT = 320    # Follow_Up, Delay_Resp, Pdelay_Resp_Follow_Up, Announce, Management
PTP_MULTICAST_IPV4 = "224.0.1.129"
PTP_DEFAULT_DOMAIN = 0

# PTP Message Types (IEEE 1588-2019)
PTP_SYNC = 0x0
PTP_DELAY_REQ = 0x1
PTP_PDELAY_REQ = 0x2
PTP_PDELAY_RESP = 0x3
PTP_FOLLOW_UP = 0x8
PTP_DELAY_RESP = 0x9
PTP_PDELAY_RESP_FOLLOW_UP = 0xA
PTP_ANNOUNCE = 0xB
PTP_SIGNALING = 0xC
PTP_MANAGEMENT = 0xD

MESSAGE_TYPES = {
    PTP_SYNC: "Sync",
    PTP_DELAY_REQ: "Delay_Req",
    PTP_PDELAY_REQ: "Pdelay_Req",
    PTP_PDELAY_RESP: "Pdelay_Resp",
    PTP_FOLLOW_UP: "Follow_Up",
    PTP_DELAY_RESP: "Delay_Resp",
    PTP_PDELAY_RESP_FOLLOW_UP: "Pdelay_Resp_Follow_Up",
    PTP_ANNOUNCE: "Announce",
    PTP_SIGNALING: "Signaling",
    PTP_MANAGEMENT: "Management"
}

# --- BrightSign Sync Constants ---
BRIGHTSIGN_DEFAULT_PORT = 5000

class BrightSignMessageType(Enum):
    """BrightSign Sync message types based on actual protocol."""
    SYNC_PRELOAD = "pre-"    # Preload next file for synchronization (prefix)
    SYNC_PLAY = "ply-"       # Play synchronized content (prefix)
    UDP_EVENT = "udp"        # Generic UDP event/command
    UNKNOWN = "unknown"

    @classmethod
    def classify(cls, message: str) -> Tuple['BrightSignMessageType', str]:
        """
        Classify a BrightSign message and extract the event name.
        Returns (message_type, event_name)
        """
        if message.startswith("pre-"):
            return (cls.SYNC_PRELOAD, message[4:])  # Remove "pre-" prefix
        elif message.startswith("ply-"):
            return (cls.SYNC_PLAY, message[4:])     # Remove "ply-" prefix
        else:
            return (cls.UDP_EVENT, message)         # Entire message is the event

class BrightSignPacket:
    """
    Parser for BrightSign Sync application messages.
    Based on actual BrightSign player implementation.

    BrightSign uses plain text UDP messages for synchronization:
    - "pre-{event}" - Preload content for synchronized event
    - "ply-{event}" - Play synchronized content
    - Any other string - Custom UDP event/command
    """

    def __init__(self, data: bytes, addr: Optional[Tuple] = None):
        self.raw_data = data
        self.src_addr = addr
        self.timestamp = datetime.datetime.now()
        self.is_valid = False
        self.message_type = BrightSignMessageType.UNKNOWN
        self.event_name = ""
        self.message_string = ""

        self._parse()

    def _parse(self):
        """Parse BrightSign sync message."""
        if len(self.raw_data) == 0:
            return

        # BrightSign messages are plain text strings
        try:
            self.message_string = self.raw_data.decode('utf-8').strip()

            # Empty or whitespace-only messages are not valid
            if not self.message_string:
                return

            self.is_valid = True

            # Classify the message type
            self.message_type, self.event_name = BrightSignMessageType.classify(self.message_string)

        except UnicodeDecodeError:
            # Not a text message - could be binary data
            # In this case, it's not a valid BrightSign message
            self.is_valid = False
    
    def __str__(self):
        if not self.is_valid:
            return f"[{self.timestamp.strftime('%H:%M:%S.%f')[:-3]}] Invalid data ({len(self.raw_data)} bytes)"

        src_info = f"{self.src_addr[0]}:{self.src_addr[1]}" if self.src_addr else "unknown"
        time_str = self.timestamp.strftime("%H:%M:%S.%f")[:-3]

        # Format based on message type
        if self.message_type == BrightSignMessageType.SYNC_PRELOAD:
            return (f"[{time_str}] {src_info:<21} | BrightSign SYNC_PRELOAD | "
                    f"Event: '{self.event_name}' | Full: '{self.message_string}'")
        elif self.message_type == BrightSignMessageType.SYNC_PLAY:
            return (f"[{time_str}] {src_info:<21} | BrightSign SYNC_PLAY    | "
                    f"Event: '{self.event_name}' | Full: '{self.message_string}'")
        else:  # UDP_EVENT
            return (f"[{time_str}] {src_info:<21} | BrightSign UDP_EVENT    | "
                    f"Command: '{self.message_string}'")

class PTPPacket:
    """Parse PTP header from UDP payload."""
    def __init__(self, data: bytes, src_addr: Optional[Tuple] = None):
        if len(data) < 34:
            raise ValueError(f"Packet too short for PTP header: {len(data)} bytes")
        
        # Parse PTP header (first 34 bytes) 
        first_byte = data[0]
        self.message_type = first_byte & 0x0F
        self.transport_specific = (first_byte >> 4) & 0x0F
        
        self.version = data[1] & 0x0F
        self.message_length = struct.unpack('>H', data[2:4])[0]
        self.domain = data[4]
        self.flags = struct.unpack('>H', data[6:8])[0]
        self.correction = struct.unpack('>Q', data[8:16])[0]
        self.clock_identity = data[20:28].hex()
        self.port_number = struct.unpack('>H', data[28:30])[0]
        self.sequence_id = struct.unpack('>H', data[30:32])[0]
        self.control = data[32]
        self.log_interval = struct.unpack('>b', bytes([data[33]]))[0]
        
        self.src_addr = src_addr
        self.timestamp = datetime.datetime.now()
    
    def __str__(self):
        msg_type_str = MESSAGE_TYPES.get(self.message_type, f"Unknown ({self.message_type})")
        clock_short = self.clock_identity[-8:] if len(self.clock_identity) > 8 else self.clock_identity
        time_str = self.timestamp.strftime("%H:%M:%S.%f")[:-3]
        
        src_info = f"{self.src_addr[0]}:{self.src_addr[1]}" if self.src_addr else "unknown"
            
        return (f"[{time_str}] {src_info:<21} | PTP {msg_type_str:<10} | "
                f"Domain: {self.domain:<3} | Seq: {self.sequence_id:<5} | "
                f"Clock: ...{clock_short}")

class MultiProtocolMonitor:
    """
    Async monitor for both PTP and BrightSign Sync protocols.
    """
    
    def __init__(self, interface_ip: str = "0.0.0.0", 
                 multicast_group: str = PTP_MULTICAST_IPV4,
                 brightsign_port: int = BRIGHTSIGN_DEFAULT_PORT,
                 enable_ptp: bool = True,
                 enable_brightsign: bool = True,
                 output_file: Optional[str] = None):
        
        self.interface_ip = interface_ip
        self.multicast_group = multicast_group
        self.brightsign_port = brightsign_port
        self.enable_ptp = enable_ptp
        self.enable_brightsign = enable_brightsign
        self.output_file = output_file
        
        self.loop = None
        self.transports = []
        self.running = False
        self.packet_count = 0
        self.ptp_count = 0
        self.brightsign_count = 0
        
        self.file_handle = None
        if output_file:
            try:
                self.file_handle = open(output_file, 'a', encoding='utf-8')
            except Exception as e:
                print(f"Warning: Could not open output file {output_file}: {e}")
        
        self._print_header()
    
    def _print_header(self):
        """Print monitoring configuration header."""
        print("=" * 90)
        print(f"Multi-Protocol Sync Monitor for Windows")
        print(f"Platform: {platform.system()} {platform.release()}")
        print(f"Interface IP: {self.interface_ip}")
        print(f"Monitoring: ", end="")
        protocols = []
        if self.enable_ptp:
            protocols.append(f"PTP (multicast {self.multicast_group}:{PTP_EVENT_PORT}/{PTP_GENERAL_PORT})")
        if self.enable_brightsign:
            protocols.append(f"BrightSign Sync (UDP port {self.brightsign_port})")
        print(", ".join(protocols))
        if self.output_file:
            print(f"Logging to: {self.output_file}")
        print("=" * 90)
    
    def create_multicast_socket(self, port: int) -> socket.socket:
        """
        Create a Windows-compatible multicast socket.
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('', port))
        
        # Join multicast group for PTP ports only
        if port in [PTP_EVENT_PORT, PTP_GENERAL_PORT]:
            mreq = struct.pack("4sl", socket.inet_aton(self.multicast_group), 
                              socket.INADDR_ANY)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)
        
        sock.setblocking(False)
        return sock
    
    def create_udp_socket(self, port: int) -> socket.socket:
        """
        Create a regular UDP socket (for BrightSign monitoring).
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('', port))
        sock.setblocking(False)
        return sock
    
    class ProtocolHandler(asyncio.DatagramProtocol):
        """Async protocol handler for all monitored protocols."""
        
        def __init__(self, monitor, port: int, protocol_type: str):
            self.monitor = monitor
            self.port = port
            self.protocol_type = protocol_type
            self.transport = None
        
        def connection_made(self, transport):
            self.transport = transport
            proto_name = "PTP" if self.protocol_type == "ptp" else "BrightSign"
            addr_info = f"multicast {self.monitor.multicast_group}" if self.protocol_type == "ptp" else f"UDP port {self.port}"
            print(f"Listening for {proto_name} on {addr_info}:{self.port}")
        
        def datagram_received(self, data: bytes, addr: Tuple):
            """Called when a datagram is received."""
            if self.monitor.loop and self.monitor.running:
                asyncio.run_coroutine_threadsafe(
                    self.monitor.handle_packet(data, addr, self.port, self.protocol_type),
                    self.monitor.loop
                )
        
        def error_received(self, exc):
            print(f"Socket error on port {self.port}: {exc}")
        
        def connection_lost(self, exc):
            if exc:
                print(f"Connection lost on port {self.port}: {exc}")
    
    async def handle_packet(self, data: bytes, addr: Tuple, port: int, protocol_type: str):
        """Process received packets from any protocol."""
        self.packet_count += 1
        
        try:
            if protocol_type == "ptp":
                packet = PTPPacket(data, src_addr=addr)
                self.ptp_count += 1
                output = str(packet)
            else:  # brightsign
                packet = BrightSignPacket(data, src_addr=addr)
                self.brightsign_count += 1
                output = str(packet)
            
            # Print to console
            print(f"[{self.packet_count:4d}] {output}")
            
            # Write to file if enabled
            if self.file_handle:
                timestamp = datetime.datetime.now().isoformat()
                self.file_handle.write(f"{timestamp},{addr[0]},{port},{output}\n")
                self.file_handle.flush()
                
        except Exception as e:
            print(f"Error handling packet on port {port}: {e}")
    
    async def start_monitoring(self):
        """Start monitoring all configured protocols."""
        self.running = True
        self.loop = asyncio.get_running_loop()
        
        # Set up PTP monitoring
        if self.enable_ptp:
            for port in [PTP_EVENT_PORT, PTP_GENERAL_PORT]:
                try:
                    sock = self.create_multicast_socket(port)
                    protocol = self.ProtocolHandler(self, port, "ptp")
                    transport, _ = await self.loop.create_datagram_endpoint(
                        lambda: protocol,
                        sock=sock
                    )
                    self.transports.append(transport)
                except Exception as e:
                    print(f"ERROR setting up PTP port {port}: {e}")
        
        # Set up BrightSign monitoring
        if self.enable_brightsign:
            try:
                sock = self.create_udp_socket(self.brightsign_port)
                protocol = self.ProtocolHandler(self, self.brightsign_port, "brightsign")
                transport, _ = await self.loop.create_datagram_endpoint(
                    lambda: protocol,
                    sock=sock
                )
                self.transports.append(transport)
            except Exception as e:
                print(f"ERROR setting up BrightSign port {self.brightsign_port}: {e}")
        
        if not self.transports:
            print("Failed to set up any listeners. Exiting.")
            return
        
        print("-" * 90)
        print(f"Monitoring active. Press Ctrl+C to stop.")
        print("-" * 90)
        
        try:
            # Keep running until stopped
            while self.running:
                await asyncio.sleep(1)
                
                # Optional: Print statistics every 30 seconds
                if self.packet_count > 0 and self.packet_count % 100 == 0:
                    print(f"Stats: Total: {self.packet_count} | "
                          f"PTP: {self.ptp_count} | "
                          f"BrightSign: {self.brightsign_count}")
                    
        except asyncio.CancelledError:
            pass
        finally:
            await self.cleanup()
    
    async def cleanup(self):
        """Clean up resources."""
        self.running = False
        for transport in self.transports:
            transport.close()
        
        if self.file_handle:
            self.file_handle.close()
        
        print(f"\nMonitoring stopped.")
        print(f"Final statistics:")
        print(f"  Total packets: {self.packet_count}")
        print(f"  PTP packets: {self.ptp_count}")
        print(f"  BrightSign packets: {self.brightsign_count}")
    
    def stop(self):
        """Stop monitoring."""
        self.running = False

async def get_interface_ip(interface_name: Optional[str] = None) -> str:
    """Get IP address of a network interface."""
    if interface_name:
        try:
            import netifaces
            iface_addrs = netifaces.ifaddresses(interface_name)
            if netifaces.AF_INET in iface_addrs:
                return iface_addrs[netifaces.AF_INET][0]['addr']
        except (ImportError, ValueError, KeyError):
            pass
    
    return "0.0.0.0"

async def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Multi-Protocol Sync Monitor for Windows")
    parser.add_argument("--interface", "-i", help="Network interface name or IP", 
                       default=None)
    parser.add_argument("--group", "-g", help="PTP multicast group address", 
                       default=PTP_MULTICAST_IPV4)
    parser.add_argument("--brightsign-port", "-b", type=int, 
                       help=f"BrightSign Sync UDP port (default: {BRIGHTSIGN_DEFAULT_PORT})", 
                       default=BRIGHTSIGN_DEFAULT_PORT)
    parser.add_argument("--output", "-o", help="Output file for logging", 
                       default=None)
    parser.add_argument("--no-ptp", action="store_true", 
                       help="Disable PTP monitoring")
    parser.add_argument("--no-brightsign", action="store_true", 
                       help="Disable BrightSign monitoring")
    
    args = parser.parse_args()
    
    # Get interface IP
    interface_ip = await get_interface_ip(args.interface)
    if args.interface and interface_ip == "0.0.0.0":
        print(f"Warning: Could not get IP for interface '{args.interface}'. "
              f"Using 0.0.0.0 (all interfaces)")
    
    # Create and start monitor
    monitor = MultiProtocolMonitor(
        interface_ip=interface_ip,
        multicast_group=args.group,
        brightsign_port=args.brightsign_port,
        enable_ptp=not args.no_ptp,
        enable_brightsign=not args.no_brightsign,
        output_file=args.output
    )
    
    try:
        await monitor.start_monitoring()
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        await monitor.cleanup()

def run_windows_event_loop():
    """Windows-specific event loop configuration."""
    if platform.system() == "Windows":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    asyncio.run(main())

if __name__ == "__main__":
    run_windows_event_loop()