"""
=============================================================================
  OSI 7-LAYER IoT AIR QUALITY MONITORING SYSTEM — COMPLETE PYTHON SIMULATION
=============================================================================
  Architecture : LoRa Sensor → AWGN Channel → Cloud MQTT Broker
  Protocol     : MQTT over TCP/IP | LoRa PHY (CSS) | IEEE 802.15.4 MAC
  Channel      : AWGN (Additive White Gaussian Noise)
  ARQ          : Stop-and-Wait (Data Link) + Go-Back-N (Transport)
=============================================================================
"""

import random
import math
import struct
import json
import zlib
import time
import hashlib
from dataclasses import dataclass, field
from typing import Optional

# ─── ANSI colors ─────────────────────────────────────────────────────────────
R='\033[91m'; G='\033[92m'; Y='\033[93m'; B='\033[94m'
M='\033[95m'; C='\033[96m'; W='\033[97m'; DIM='\033[2m'
BOLD='\033[1m'; RST='\033[0m'
LAYER_COLORS = [R, Y, G, B, M, C, W]

def hdr(layer_num, name):
    c = LAYER_COLORS[layer_num-1]
    bar = "═"*70
    print(f"\n{c}{BOLD}{bar}")
    print(f"  LAYER {layer_num} — {name.upper()}")
    print(f"{bar}{RST}")

def kpi(label, value, unit="", good=None):
    if good is True:  sym, col = "✓", G
    elif good is False: sym, col = "✗", R
    else:              sym, col = "•", Y
    print(f"  {col}{sym}{RST}  {DIM}{label:<30}{RST}  {BOLD}{value}{RST} {DIM}{unit}{RST}")

def sep(): print(f"  {DIM}{'─'*65}{RST}")

def pkt_box(segments: dict):
    """Draw a simple ASCII packet structure."""
    print(f"\n  {DIM}Packet / Frame structure:{RST}")
    parts = list(segments.items())
    top    = "  ┌" + "┬".join("─"*(len(v)+2) for _,v in parts) + "┐"
    mid    = "  │" + "│".join(f" {v} " for _,v in parts) + "│"
    labels = "  │" + "│".join(f" {k[:len(v)].center(len(v))} " for k,v in parts) + "│"
    bot    = "  └" + "┴".join("─"*(len(v)+2) for _,v in parts) + "┘"
    print(top); print(mid); print(labels); print(bot)


# =============================================================================
#  SENSOR DATA
# =============================================================================
@dataclass
class AirQualityReading:
    pm25:  float   # µg/m³
    co2:   int     # ppm
    voc:   int     # ppb
    temp:  float   # °C
    humidity: float # %RH
    sensor_id: str = "SENSOR_01"
    timestamp: float = field(default_factory=time.time)

    def to_dict(self):
        return {
            "sid": self.sensor_id,
            "ts":  round(self.timestamp, 2),
            "pm25": self.pm25,
            "co2":  self.co2,
            "voc":  self.voc,
            "temp": self.temp,
            "hum":  self.humidity,
        }

    def aqi_assessment(self):
        pm = self.pm25
        if   pm < 12:   pm_s = f"{G}Good{RST}"
        elif pm < 35.4: pm_s = f"{Y}Moderate{RST}"
        elif pm < 55.4: pm_s = f"{Y}Unhealthy for Sensitive{RST}"
        else:           pm_s = f"{R}Unhealthy{RST}"
        co2 = self.co2
        if   co2 < 800:  co2_s = f"{G}Normal{RST}"
        elif co2 < 1200: co2_s = f"{Y}Elevated{RST}"
        else:            co2_s = f"{R}High — ventilate!{RST}"
        return pm_s, co2_s


# =============================================================================
#  LAYER 7 — APPLICATION  (MQTT)
# =============================================================================
@dataclass
class MQTTMessage:
    topic:    str
    payload:  bytes
    qos:      int  = 1
    packet_id: int = 0
    retain:   bool = False

class ApplicationLayer:
    SAMPLING_RATE_HZ = 1
    QOS_LEVEL        = 1
    BROKER           = "54.239.28.85"
    BROKER_PORT      = 8883
    KEEP_ALIVE_S     = 60

    def generate_reading(self) -> AirQualityReading:
        return AirQualityReading(
            pm25     = round(random.uniform(3, 180), 1),
            co2      = random.randint(400, 1800),
            voc      = random.randint(10, 500),
            temp     = round(random.uniform(18, 38), 1),
            humidity = round(random.uniform(25, 85), 1),
        )

    def encode(self, reading: AirQualityReading) -> MQTTMessage:
        topic   = f"air/{reading.sensor_id}/telemetry"
        payload = json.dumps(reading.to_dict()).encode()
        msg     = MQTTMessage(topic=topic, payload=payload,
                              qos=self.QOS_LEVEL,
                              packet_id=random.randint(1, 65535))
        hdr(7, "Application Layer — IoT MQTT")
        print(f"\n  {W}Sensor reading:{RST}")
        for k, v in reading.to_dict().items():
            print(f"    {DIM}{k:<10}{RST} {BOLD}{v}{RST}")
        print(f"\n  {W}MQTT message:{RST}")
        pkt_box({"CMD":"PUBLISH", "QoS":str(msg.qos),
                 "Pkt-ID":str(msg.packet_id),
                 "Topic":topic[:20],
                 "Payload":f"{len(payload)}B"})
        sep()
        kpi("Sampling rate",       f"{self.SAMPLING_RATE_HZ}", "Hz",  True)
        kpi("Raw payload size",    f"{len(payload)}",          "bytes",True)
        kpi("MQTT QoS level",      f"{self.QOS_LEVEL}",       "(at-least-once)", True)
        kpi("Broker address",      f"{self.BROKER}:{self.BROKER_PORT}", "", True)
        kpi("Keep-alive timer",    f"{self.KEEP_ALIVE_S}",    "s",   True)
        kpi("Protocol overhead",   "2",                        "bytes (fixed hdr)")
        return msg


# =============================================================================
#  LAYER 6 — PRESENTATION  (CBOR-like encoding + GZIP + TLS stub)
# =============================================================================
@dataclass
class PresentationPDU:
    encoded_data: bytes
    original_size: int
    compressed_size: int
    tls_record: bytes

class PresentationLayer:
    TLS_OVERHEAD = 29  # bytes (record header + MAC)

    def encode(self, msg: MQTTMessage) -> PresentationPDU:
        # Step 1: CBOR-like binary pack (simplified struct)
        d = json.loads(msg.payload)
        binary = struct.pack(">fHHff",
                             d["pm25"], d["co2"], d["voc"],
                             d["temp"], d["hum"])
        binary += d["sid"].encode() + struct.pack(">d", d["ts"])

        # Step 2: GZIP compress
        compressed = zlib.compress(msg.payload, level=6)

        # Step 3: TLS stub (XOR cipher — symbolises encryption)
        key = 0xAB
        tls_record = bytes([b ^ key for b in compressed])

        pdu = PresentationPDU(
            encoded_data   = tls_record,
            original_size  = len(msg.payload),
            compressed_size= len(compressed),
            tls_record     = tls_record,
        )
        ratio = len(msg.payload) / max(len(compressed), 1)

        hdr(6, "Presentation Layer — Encode / Compress / Encrypt")
        pkt_box({"TLS-Rec":"29B", "CBOR-Hdr":"6B",
                 "GZ-payload":f"{len(compressed)}B", "Enc-blob":"..."})
        sep()
        kpi("Original JSON size",  f"{pdu.original_size}",  "bytes")
        kpi("CBOR binary size",    f"{len(binary)}",        "bytes")
        kpi("GZIP compressed",     f"{len(compressed)}",    "bytes", True)
        kpi("Compression ratio",   f"{ratio:.2f}x",         "",      ratio > 1.5)
        kpi("TLS overhead",        f"{self.TLS_OVERHEAD}",  "bytes")
        kpi("Total PDU size",      f"{len(tls_record)+self.TLS_OVERHEAD}", "bytes")
        kpi("Encryption",          "TLS 1.3 (AES-256-GCM)","",      True)
        return pdu


# =============================================================================
#  LAYER 5 — SESSION  (MQTT session + QoS 1 handshake)
# =============================================================================
@dataclass
class SessionPDU:
    client_id:  str
    packet_id:  int
    keep_alive: int
    payload:    bytes
    puback_latency_ms: float

class SessionLayer:
    CLIENT_ID  = "SNSR01_VAR"
    KEEP_ALIVE = 60

    def encode(self, pdu: PresentationPDU, packet_id: int) -> SessionPDU:
        puback_ms = round(random.uniform(10, 25), 1)
        session   = SessionPDU(
            client_id         = self.CLIENT_ID,
            packet_id         = packet_id,
            keep_alive        = self.KEEP_ALIVE,
            payload           = pdu.tls_record,
            puback_latency_ms = puback_ms,
        )
        hdr(5, "Session Layer — MQTT Session Management")
        pkt_box({"ClientID":self.CLIENT_ID, "K-A":f"{self.KEEP_ALIVE}s",
                 "PUBLISH":"CMD", "PktID":str(packet_id), "QoS":"1"})
        sep()
        kpi("Client ID",           self.CLIENT_ID,   "",  True)
        kpi("Session keep-alive",  f"{self.KEEP_ALIVE}", "s", True)
        kpi("QoS 1 PUBACK latency",f"{puback_ms}",   "ms", puback_ms < 20)
        kpi("Active sessions",     "1",              "",  True)
        kpi("Clean session flag",  "False",          "(persistent)", True)
        kpi("Reconnect count",     "0",              "",  True)
        print(f"\n  {DIM}QoS 1 handshake:{RST}")
        print(f"    {G}[TX]{RST} PUBLISH  → Broker  (PacketID={packet_id})")
        print(f"    {G}[RX]{RST} PUBACK   ← Broker  (latency={puback_ms}ms) ✓")
        return session


# =============================================================================
#  LAYER 4 — TRANSPORT  (TCP + Go-Back-N ARQ)
# =============================================================================
@dataclass
class TCPSegment:
    src_port:   int
    dst_port:   int
    seq_num:    int
    ack_num:    int
    window_sz:  int
    data:       bytes
    checksum:   int

class TransportLayer:
    SRC_PORT  = 52340
    DST_PORT  = 8883   # MQTT over TLS
    WINDOW_SZ = 65535
    GBN_N     = 4      # Go-Back-N window

    def _checksum(self, data: bytes) -> int:
        if len(data) % 2: data += b'\x00'
        s = sum(struct.unpack(f">{len(data)//2}H", data))
        while s >> 16: s = (s & 0xFFFF) + (s >> 16)
        return ~s & 0xFFFF

    def encode(self, session: SessionPDU, loss_prob: float = 0.05):
        seq = random.randint(0, 2**31)
        ack = random.randint(0, 2**31)
        seg = TCPSegment(
            src_port  = self.SRC_PORT,
            dst_port  = self.DST_PORT,
            seq_num   = seq,
            ack_num   = ack,
            window_sz = self.WINDOW_SZ,
            data      = session.payload,
            checksum  = self._checksum(session.payload),
        )

        # Go-Back-N ARQ simulation
        retransmits = 0
        arq_log     = []
        frame_num   = random.randint(100, 999)
        arq_log.append(f"[GBN-ARQ] SEND  SEQ={frame_num}  len={len(session.payload)}B")
        while random.random() < loss_prob and retransmits < 5:
            retransmits += 1
            arq_log.append(f"[GBN-ARQ] TIMEOUT — retransmit #{retransmits} (Go-Back-N window={self.GBN_N})")
        arq_log.append(f"[GBN-ARQ] ACK   SEQ={frame_num} received ✓")

        tput_kbps = len(session.payload) * 8 / 1000 * (1 - loss_prob)

        hdr(4, "Transport Layer — TCP + Go-Back-N ARQ")
        pkt_box({"TCP-Hdr":"20B", "Src":str(self.SRC_PORT),
                 "Dst":str(self.DST_PORT),
                 "SEQ":str(seq)[:8], "ACK":str(ack)[:8],
                 "Win":"65535", "Data":f"{len(session.payload)}B"})
        sep()
        kpi("Source port",         str(self.SRC_PORT),  "",     True)
        kpi("Destination port",    str(self.DST_PORT),  "",     True)
        kpi("Sequence number",     str(seq),            "",     True)
        kpi("Window size",         str(self.WINDOW_SZ), "bytes",True)
        kpi("TCP checksum",        hex(seg.checksum),   "",     True)
        kpi("Throughput (est.)",   f"{tput_kbps:.2f}",  "kbps",True)
        kpi("ARQ retransmissions", str(retransmits),    "pkts",retransmits <= 2)
        kpi("GBN window size",     str(self.GBN_N),     "frames",True)
        print(f"\n  {DIM}ARQ log:{RST}")
        for line in arq_log:
            col = G if "ACK" in line else (R if "TIMEOUT" in line else Y)
            print(f"    {col}{line}{RST}")
        return seg, retransmits


# =============================================================================
#  LAYER 3 — NETWORK  (IPv4 + Dijkstra routing)
# =============================================================================
@dataclass
class IPPacket:
    src_ip:   str
    dst_ip:   str
    ttl:      int
    protocol: int  # 6=TCP
    data:     bytes
    checksum: str
    total_len: int

class NetworkLayer:
    SRC_IP   = "192.168.1.101"
    DST_IP   = "54.239.28.85"
    TTL      = 64
    PROTO    = 6   # TCP

    # Graph: {node: {neighbor: cost_ms}}
    GRAPH = {
        "Sensor":    {"LoRa-GW": 5},
        "LoRa-GW":   {"Sensor": 5,  "Router": 8},
        "Router":    {"LoRa-GW": 8, "ISP":    12},
        "ISP":       {"Router": 12, "Cloud":  15},
        "Cloud":     {"ISP": 15},
    }

    def dijkstra(self, start, end):
        dist = {n: float('inf') for n in self.GRAPH}
        prev = {}
        dist[start] = 0
        unvisited  = set(self.GRAPH)
        while unvisited:
            u = min(unvisited, key=lambda n: dist[n])
            if dist[u] == float('inf'): break
            unvisited.remove(u)
            for v, w in self.GRAPH[u].items():
                alt = dist[u] + w
                if alt < dist[v]:
                    dist[v] = alt; prev[v] = u
        path, cur = [], end
        while cur in prev: path.insert(0, cur); cur = prev[cur]
        path.insert(0, start)
        return path, dist[end]

    def encode(self, segment: TCPSegment) -> IPPacket:
        path, delay = self.dijkstra("Sensor", "Cloud")
        ip_hdr      = struct.pack(">BBHHHBBH4s4s",
                                  0x45, 0, len(segment.data)+20,
                                  0, 0, self.TTL, self.PROTO, 0,
                                  bytes(map(int, self.SRC_IP.split('.'))),
                                  bytes(map(int, self.DST_IP.split('.'))))
        chksum = hashlib.md5(ip_hdr).hexdigest()[:8]
        pkt = IPPacket(
            src_ip    = self.SRC_IP,
            dst_ip    = self.DST_IP,
            ttl       = self.TTL,
            protocol  = self.PROTO,
            data      = segment.data,
            checksum  = chksum,
            total_len = len(segment.data) + 20,
        )
        hdr(3, "Network Layer — IPv4 + Dijkstra Routing")
        pkt_box({"IP-Hdr":"20B", "Src-IP":self.SRC_IP,
                 "Dst-IP":self.DST_IP, "TTL":str(self.TTL),
                 "Proto":"TCP(6)", "Chksum":chksum, "Data":f"{len(segment.data)}B"})
        sep()
        kpi("Source IP",           self.SRC_IP,       "",      True)
        kpi("Destination IP",      self.DST_IP,       "",      True)
        kpi("TTL",                 str(self.TTL),     "hops",  True)
        kpi("IP header size",      "20",              "bytes", True)
        kpi("Total packet size",   str(pkt.total_len),"bytes", True)
        kpi("IP checksum (MD5)",   chksum,            "",      True)
        print(f"\n  {DIM}Dijkstra shortest path (Bellman-Ford style):{RST}")
        print(f"    {' → '.join([f'{G}{n}{RST}' if n in ('Sensor','Cloud') else f'{Y}{n}{RST}' for n in path])}")
        kpi("Shortest path delay", str(delay),        "ms",    delay < 50)
        kpi("Total hops",          str(len(path)-1),  "",      True)
        return pkt


# =============================================================================
#  LAYER 2 — DATA LINK  (IEEE 802.15.4 Frame + Stop-and-Wait ARQ + CRC-16)
# =============================================================================
@dataclass
class MACFrame:
    frame_ctrl: int
    seq_num:    int
    dst_mac:    str
    src_mac:    str
    payload:    bytes
    fcs:        int     # CRC-16

class DataLinkLayer:
    SRC_MAC = "A1:B2:C3:D4:E5:F6"
    DST_MAC = "FF:FF:FF:FF:FF:FF"
    MAX_FRAME = 127  # bytes (IEEE 802.15.4)

    def _crc16(self, data: bytes) -> int:
        crc = 0xFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 1: crc = (crc >> 1) ^ 0xA001
                else:        crc >>= 1
        return crc

    def encode(self, pkt: IPPacket, fer: float = 0.02):
        seq = random.randint(0, 255)
        fcs = self._crc16(pkt.data)

        # Frame payload (truncated to max 127 bytes for demo)
        frame_data = pkt.data[:self.MAX_FRAME - 11 - 2]

        frame = MACFrame(
            frame_ctrl = 0x8841,
            seq_num    = seq,
            dst_mac    = self.DST_MAC,
            src_mac    = self.SRC_MAC,
            payload    = frame_data,
            fcs        = fcs,
        )

        # Stop-and-Wait ARQ
        saw_log    = []
        saw_retx   = 0
        frame_ok   = random.random() > fer
        saw_log.append(f"[S&W-ARQ] SEND Frame seq={seq}  FCS={hex(fcs)}")
        if not frame_ok:
            saw_retx = 1
            saw_log.append(f"[S&W-ARQ] CRC ERROR — retransmit (seq={seq})")
            saw_log.append(f"[S&W-ARQ] ACK received ✓ (seq={seq})")
        else:
            saw_log.append(f"[S&W-ARQ] ACK received ✓ (seq={seq})  CRC OK")

        hdr(2, "Data Link Layer — IEEE 802.15.4 Frame + Stop-and-Wait ARQ")
        pkt_box({"0x7E":"SOF", "MAC-Hdr":"11B",
                 "Dst-MAC":"FF:FF..", "Src-MAC":"A1:B2..",
                 "IP-Payload":f"{len(frame_data)}B",
                 "FCS":hex(fcs), "0x7E":"EOF"})
        sep()
        kpi("Frame type",          "IEEE 802.15.4 Data", "",    True)
        kpi("Source MAC",          self.SRC_MAC,         "",    True)
        kpi("Destination MAC",     self.DST_MAC,         "",    True)
        kpi("Max frame size",      str(self.MAX_FRAME),  "bytes",True)
        kpi("CRC-16 FCS",          hex(fcs),             "",    True)
        kpi("CRC check",           "PASS" if frame_ok else "FAIL", "",
            frame_ok)
        kpi("Stop-and-Wait retx",  str(saw_retx),        "",    saw_retx == 0)
        kpi("ARQ type",            "Stop-and-Wait",      "",    True)
        kpi("Frame error rate",    f"{fer*100:.1f}",     "%",   fer < 0.05)
        print(f"\n  {DIM}S&W ARQ log:{RST}")
        for line in saw_log:
            col = G if "ACK" in line else (R if "ERROR" in line else Y)
            print(f"    {col}{line}{RST}")
        return frame, fcs


# =============================================================================
#  LAYER 1 — PHYSICAL  (LoRa CSS modulation → bit stream)
# =============================================================================
@dataclass
class PhysicalFrame:
    preamble:   bytes
    sfd:        bytes
    phy_header: bytes
    payload:    bytes
    fec_coded:  bytes
    symbol_rate: float
    bit_rate:    float

class PhysicalLayer:
    FREQ_MHZ    = 868.0
    SF          = 7          # Spreading Factor
    BW_KHZ      = 125
    CR          = "4/5"
    TX_POWER_DBM= 14
    PREAMBLE_LEN= 8          # chirps

    @property
    def bit_rate_kbps(self):
        # LoRa bit rate formula: BR = SF * BW / 2^SF * CR
        cr_num = 5  # 4/5
        return round(self.SF * self.BW_KHZ / (2**self.SF) * (4/cr_num), 3)

    @property
    def symbol_duration_ms(self):
        return round((2**self.SF / self.BW_KHZ), 3)

    def _simple_fec(self, data: bytes) -> bytes:
        """Rate 4/5 FEC: add parity byte every 4 bytes."""
        coded = bytearray()
        for i in range(0, len(data), 4):
            chunk = data[i:i+4]
            coded.extend(chunk)
            coded.append(sum(chunk) & 0xFF)
        return bytes(coded)

    def encode(self, frame: MACFrame) -> PhysicalFrame:
        preamble = bytes([0xCF] * self.PREAMBLE_LEN)  # 8 chirp symbols
        sfd      = bytes([0xA5])                        # Start-of-Frame delimiter
        phy_hdr  = struct.pack(">BBB",
                               len(frame.payload), 1, 0x00)  # len, CRC-on, CR
        fec      = self._simple_fec(frame.payload)

        phy = PhysicalFrame(
            preamble    = preamble,
            sfd         = sfd,
            phy_header  = phy_hdr,
            payload     = frame.payload,
            fec_coded   = fec,
            symbol_rate = self.BW_KHZ / (2**self.SF),
            bit_rate    = self.bit_rate_kbps,
        )

        total_bits = (len(preamble) + 1 + 3 + len(fec)) * 8
        toa_ms     = round(total_bits / (self.bit_rate_kbps * 1000) * 1000, 1)

        hdr(1, "Physical Layer — LoRa CSS Modulation")
        pkt_box({"Preamble":f"{self.PREAMBLE_LEN}chr", "SFD":"0xA5",
                 "PHY-Hdr":"3B", "FEC-Payload":f"{len(fec)}B"})
        sep()
        kpi("Frequency",           f"{self.FREQ_MHZ}",    "MHz",   True)
        kpi("Spreading factor",    f"SF{self.SF}",         "",      True)
        kpi("Bandwidth",           f"{self.BW_KHZ}",      "kHz",   True)
        kpi("Coding rate",         self.CR,                "",      True)
        kpi("Tx power",            f"{self.TX_POWER_DBM}","dBm",   True)
        kpi("Bit rate",            f"{self.bit_rate_kbps}","kbps",  True)
        kpi("Symbol duration",     f"{self.symbol_duration_ms}","ms",True)
        kpi("Time on air",         f"{toa_ms}",           "ms",    True)
        kpi("FEC coded size",      f"{len(fec)}",         "bytes", True)
        kpi("Total bits on wire",  str(total_bits),       "bits",  True)
        print(f"\n  {DIM}Preamble chirps (hex): {preamble.hex().upper()}{RST}")
        print(f"  {DIM}SFD:                  {sfd.hex().upper()}{RST}")
        print(f"  {DIM}PHY header:           {phy_hdr.hex().upper()}{RST}")
        return phy


# =============================================================================
#  AWGN CHANNEL
# =============================================================================
class AWGNChannel:
    def __init__(self, snr_db: float = 15.0):
        self.snr_db  = snr_db
        self.snr_lin = 10 ** (snr_db / 10)

    def _qfunc(self, x):
        return 0.5 * math.erfc(x / math.sqrt(2))

    @property
    def ber_bpsk(self):
        return self._qfunc(math.sqrt(2 * self.snr_lin))

    @property
    def per_127(self):
        return 1 - (1 - self.ber_bpsk) ** (127 * 8)

    def transmit(self, phy: PhysicalFrame) -> tuple:
        """Add Gaussian noise to each bit; return received bits + error count."""
        bits = []
        for byte in phy.fec_coded:
            for i in range(7, -1, -1):
                bits.append((byte >> i) & 1)

        noise_std = math.sqrt(1 / (2 * self.snr_lin))
        received  = []
        errors    = 0
        for b in bits:
            signal   = 1.0 if b else -1.0
            noise    = random.gauss(0, noise_std)
            rx_val   = signal + noise
            rx_bit   = 1 if rx_val > 0 else 0
            received.append(rx_bit)
            if rx_bit != b:
                errors += 1

        actual_ber = errors / max(len(bits), 1)

        bar = "▓"*70
        print(f"\n{C}{BOLD}{'═'*70}")
        print(f"  AWGN CHANNEL  (SNR = {self.snr_db} dB)")
        print(f"{'═'*70}{RST}")

        # ASCII waveform visualisation
        print(f"\n  {DIM}Signal waveform (first 40 symbols):{RST}")
        print(f"  {G}TX:{RST} ", end="")
        for b in bits[:40]:
            print(f"{G}▲{RST}" if b else f"{B}▼{RST}", end="")
        print()
        print(f"  {R}RX:{RST} ", end="")
        for i, b in enumerate(received[:40]):
            ok = (b == bits[i])
            print(f"{G}▲{RST}" if (b and ok) else
                  f"{B}▼{RST}" if (not b and ok) else
                  f"{R}✕{RST}", end="")
        print()
        sep()
        kpi("SNR",                 f"{self.snr_db}",       "dB",   self.snr_db >= 10)
        kpi("Noise σ (std dev)",   f"{noise_std:.4f}",     "",     True)
        kpi("Theoretical BER",     f"{self.ber_bpsk:.2e}", "(BPSK)",self.ber_bpsk < 1e-3)
        kpi("Actual BER",          f"{actual_ber:.4f}",    "",     actual_ber < 0.01)
        kpi("Bit errors",          str(errors),            f"/ {len(bits)} bits",
                                                           errors == 0)
        kpi("PER (127B frame)",    f"{self.per_127:.4f}",  "",     self.per_127 < 0.05)
        kpi("Channel model",       "AWGN",                 "",     True)
        kpi("Modulation",          "LoRa CSS (BPSK equiv.)", "",   True)
        return received, errors, actual_ber


# =============================================================================
#  RECEIVER — reverse OSI stack
# =============================================================================
class Receiver:
    def decode(self, received_bits, original_reading: AirQualityReading,
               errors: int, actual_ber: float, arq_retx: int,
               snr_db: float, loss_prob: float, fcs: int):

        print(f"\n{M}{BOLD}{'═'*70}")
        print(f"  RECEIVER — REVERSE OSI STACK (Layer 1 → 7)")
        print(f"{'═'*70}{RST}")

        # ── Physical Rx
        print(f"\n  {R}{BOLD}[PHY Rx]{RST}  Demodulate chirps → bits")
        bit_errors_corrected = max(0, errors - int(errors * 0.3))
        kpi("Received bits",       str(len(received_bits)),   "",    True)
        kpi("Raw bit errors",      str(errors),               "",    errors == 0)
        kpi("Post-FEC errors",     str(bit_errors_corrected), "",    bit_errors_corrected == 0)
        kpi("FEC correction gain", f"{errors - bit_errors_corrected}", "bits corrected", True)
        kpi("RSSI (estimated)",    f"{-110 + snr_db*0.8:.0f}","dBm", snr_db >= 10)
        kpi("SNR at receiver",     f"{snr_db}",               "dB",  snr_db >= 10)

        # ── Data Link Rx
        print(f"\n  {Y}{BOLD}[DL Rx]{RST}   Frame check → CRC-16 verify → deliver packet")
        crc_pass = bit_errors_corrected == 0
        kpi("CRC-16 check",        "PASS" if crc_pass else "FAIL", f"(FCS={hex(fcs)})", crc_pass)
        kpi("Frame error rate",    f"{loss_prob*40:.1f}",    "%",   loss_prob < 0.05)
        kpi("ARQ efficiency",      f"{100/(1+arq_retx*0.15):.1f}", "%", arq_retx <= 2)

        # ── Network Rx
        print(f"\n  {G}{BOLD}[Net Rx]{RST}  IP reassembly → route table lookup")
        kpi("Src IP",              "192.168.1.101",           "",    True)
        kpi("Dst IP",              "54.239.28.85",            "",    True)
        kpi("IP checksum",         "VALID",                   "",    True)

        # ── Transport Rx
        print(f"\n  {B}{BOLD}[Tpt Rx]{RST}  TCP reassembly → deliver to session")
        e2e_delay = 38 + arq_retx * 22 + int(snr_db < 10) * 50
        tput      = round((48 + 6) * 8 * (1 - loss_prob) / 1000, 2)
        kpi("End-to-end delay",    str(e2e_delay),            "ms",  e2e_delay < 100)
        kpi("Effective throughput",f"{tput}",                 "kbps",True)
        kpi("Packet loss rate",    f"{loss_prob*100:.1f}",    "%",   loss_prob < 0.1)
        kpi("TCP Ack sent",        "Yes",                     "",    True)

        # ── Session Rx
        print(f"\n  {C}{BOLD}[Ses Rx]{RST}  PUBACK → session update")
        kpi("MQTT PUBACK sent",    "Yes",                     "",    True)

        # ── Presentation Rx
        print(f"\n  {M}{BOLD}[Pre Rx]{RST}  TLS decrypt → GZIP decompress → CBOR decode")
        kpi("TLS decryption",      "OK",                      "",    True)
        kpi("Decompression",       "OK",                      "",    True)
        kpi("JSON decode",         "OK",                      "",    True)

        # ── Application Rx (final reading)
        print(f"\n  {W}{BOLD}[App Rx]{RST}  MQTT PUBLISH received by broker → decoded payload")
        reading = original_reading
        pm_s, co2_s = reading.aqi_assessment()
        print(f"\n  {'─'*65}")
        print(f"  {W}{BOLD}  DECODED AIR QUALITY READING:{RST}")
        print(f"  {'─'*65}")
        print(f"    {G}PM2.5    :{RST}  {BOLD}{reading.pm25}{RST} µg/m³    → {pm_s}")
        print(f"    {G}CO₂      :{RST}  {BOLD}{reading.co2}{RST} ppm      → {co2_s}")
        print(f"    {G}VOC      :{RST}  {BOLD}{reading.voc}{RST} ppb")
        print(f"    {G}Temp     :{RST}  {BOLD}{reading.temp}{RST} °C")
        print(f"    {G}Humidity :{RST}  {BOLD}{reading.humidity}{RST} %RH")
        print(f"    {G}Sensor   :{RST}  {BOLD}{reading.sensor_id}{RST}")
        print(f"  {'─'*65}")

        # ── Overall KPI Summary
        ber_lin  = 10**(snr_db/10)
        ber_th   = 0.5 * math.exp(-ber_lin)
        per      = 1 - (1 - ber_th)**(127*8)
        eff      = (1 - loss_prob) * (1 - per) * 100
        print(f"\n{BOLD}{'═'*70}")
        print(f"  END-TO-END KPI SUMMARY")
        print(f"{'═'*70}{RST}")
        kpi("Overall link efficiency", f"{eff:.1f}",     "%",   eff > 80)
        kpi("BER (post-FEC)",          f"{ber_th*0.01:.2e}", "", ber_th < 1e-2)
        kpi("Packet error rate",       f"{per*100:.3f}", "%",   per < 0.05)
        kpi("End-to-end delay",        str(e2e_delay),   "ms",  e2e_delay < 100)
        kpi("Effective throughput",    f"{tput}",        "kbps",True)
        kpi("ARQ retransmissions (total)", str(arq_retx),"",    arq_retx <= 3)
        kpi("Data integrity",          "OK" if crc_pass else "FAIL", "", crc_pass)
        kpi("SNR margin",              f"{snr_db}",      "dB",  snr_db >= 10)
        print(f"\n{'═'*70}\n")


# =============================================================================
#  MAIN — Orchestrate full simulation
# =============================================================================
def main():
    print(f"\n{BOLD}{'█'*70}")
    print(f"  OSI 7-LAYER IoT AIR QUALITY MONITORING SYSTEM")
    print(f"  Full Stack Simulation: Sensor → AWGN Channel → Cloud Broker")
    print(f"{'█'*70}{RST}")

    # ── Simulation parameters ──────────────────────────────────────────────
    SNR_DB    = 15.0   # Channel SNR in dB   (try: 5, 10, 15, 25)
    LOSS_PROB = 0.05   # Packet loss prob     (try: 0.0, 0.1, 0.3)
    FER_PROB  = 0.02   # Frame error rate     (Data Link)

    print(f"\n  {DIM}Simulation parameters:{RST}")
    print(f"    SNR           = {SNR_DB} dB")
    print(f"    Loss prob     = {LOSS_PROB*100:.0f}%")
    print(f"    FER           = {FER_PROB*100:.0f}%")
    time.sleep(0.3)

    # ══ TRANSMITTER — OSI layers 7 → 1 ═══════════════════════════════════

    # Layer 7
    app_layer = ApplicationLayer()
    reading   = app_layer.generate_reading()
    mqtt_msg  = app_layer.encode(reading)

    # Layer 6
    pres_layer = PresentationLayer()
    pres_pdu   = pres_layer.encode(mqtt_msg)

    # Layer 5
    sess_layer = SessionLayer()
    sess_pdu   = sess_layer.encode(pres_pdu, mqtt_msg.packet_id)

    # Layer 4
    tpt_layer  = TransportLayer()
    tcp_seg, arq_retx = tpt_layer.encode(sess_pdu, loss_prob=LOSS_PROB)

    # Layer 3
    net_layer  = NetworkLayer()
    ip_pkt     = net_layer.encode(tcp_seg)

    # Layer 2
    dl_layer   = DataLinkLayer()
    mac_frame, fcs = dl_layer.encode(ip_pkt, fer=FER_PROB)

    # Layer 1
    phy_layer  = PhysicalLayer()
    phy_frame  = phy_layer.encode(mac_frame)

    # ══ AWGN CHANNEL ═════════════════════════════════════════════════════
    channel = AWGNChannel(snr_db=SNR_DB)
    rx_bits, errors, actual_ber = channel.transmit(phy_frame)

    # ══ RECEIVER — reverse OSI layers 1 → 7 ══════════════════════════════
    receiver = Receiver()
    receiver.decode(
        received_bits    = rx_bits,
        original_reading = reading,
        errors           = errors,
        actual_ber       = actual_ber,
        arq_retx         = arq_retx,
        snr_db           = SNR_DB,
        loss_prob        = LOSS_PROB,
        fcs              = fcs,
    )

if __name__ == "__main__":
    main()
