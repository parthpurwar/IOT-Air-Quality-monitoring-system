# IOT-Air-Quality-monitoring-system

**Authors:**
> - **Yashu (Roll No:- 23095125)**
> - **Parmesh Rana (Roll No:- 23095070)**
> - **Priyanshu Baderia (Roll No:- 23095075)**


A complete end-to-end Python simulation of an IoT-based Air Quality Monitoring System built using the **OSI 7-Layer Architecture**.  
The project demonstrates how sensor data travels from an IoT sensor node to a cloud MQTT broker through different communication layers, including realistic networking concepts such as:

- MQTT over TCP/IP
- LoRa PHY communication
- IEEE 802.15.4 MAC framing
- AWGN wireless channel simulation
- ARQ protocols
- CRC error checking
- Dijkstra routing
- Compression & encryption

This simulation visually explains how real-world IoT communication systems work internally.

---

# Project Overview

The system simulates:

```text
Air Quality Sensor
        ↓
Application Layer (MQTT)
        ↓
Presentation Layer (Compression + Encryption)
        ↓
Session Layer (MQTT Session)
        ↓
Transport Layer (TCP + Go-Back-N ARQ)
        ↓
Network Layer (IPv4 + Routing)
        ↓
Data Link Layer (IEEE 802.15.4 + CRC + Stop-and-Wait)
        ↓
Physical Layer (LoRa CSS Modulation)
        ↓
AWGN Wireless Channel
        ↓
Receiver (Reverse OSI Stack)
        ↓
Cloud MQTT Broker
```

---

# Features

## Complete OSI Layer Simulation
Implements all 7 OSI layers individually with realistic functionality.

## IoT Air Quality Monitoring
Simulates sensor readings including:
- PM2.5
- CO₂
- VOC
- Temperature
- Humidity

## MQTT Communication
Implements MQTT publish messaging with:
- QoS handling
- Packet IDs
- Session management
- PUBACK simulation

## LoRa Physical Layer
Simulates:
- Chirp Spread Spectrum (CSS)
- Spreading Factor
- Coding Rate
- Time on Air
- Symbol Rate

## Wireless Channel Simulation
Implements an AWGN (Additive White Gaussian Noise) channel model for realistic wireless transmission.

## Error Detection & Recovery
Includes:
- CRC-16 checking
- Stop-and-Wait ARQ
- Go-Back-N ARQ

## Routing Simulation
Uses Dijkstra shortest-path routing algorithm.

## Security & Compression
Implements:
- TLS-like encryption simulation
- GZIP compression
- Binary encoding

## Rich Console Visualization
Provides:
- Colored outputs
- Packet structures
- KPI summaries
- Waveform visualization
- OSI layer breakdowns

---

# Technologies Used

- Python 3
- Dataclasses
- JSON
- Struct Packing
- Zlib Compression
- Hashlib
- Random Noise Simulation
- Networking Concepts
- IoT Protocol Simulation

---

# System Architecture

## Layer-wise Architecture

| OSI Layer | Implementation |
|---|---|
| Layer 7 | MQTT Application Protocol |
| Layer 6 | Compression + Encryption |
| Layer 5 | MQTT Session Management |
| Layer 4 | TCP + Go-Back-N ARQ |
| Layer 3 | IPv4 + Dijkstra Routing |
| Layer 2 | IEEE 802.15.4 + CRC + Stop-and-Wait |
| Layer 1 | LoRa CSS Modulation |

---

# Key Networking Concepts Implemented

## Application Layer
- MQTT Publish Messages
- QoS 1 Delivery
- Topic-based communication

## Presentation Layer
- Binary encoding
- Compression
- TLS-style encryption

## Session Layer
- MQTT sessions
- Keep-alive timers
- PUBACK handling

## Transport Layer
- TCP segmentation
- Sequence numbers
- Sliding window
- Go-Back-N ARQ

## Network Layer
- IPv4 packet creation
- Routing
- TTL handling
- Dijkstra shortest path algorithm

## Data Link Layer
- MAC framing
- CRC-16
- Stop-and-Wait ARQ

## Physical Layer
- LoRa PHY
- FEC coding
- Bitstream generation
- Time-on-air calculation

---

# Installation

## Clone the Repository

```bash
git clone https://github.com/your-username/osi-iot-air-quality-system.git
cd osi-iot-air-quality-system
```

## Run the Simulation

```bash
python main.py
```

---

# Example Output

The simulation displays:

- Sensor readings
- MQTT packet details
- TCP/IP packet structures
- MAC frames
- LoRa PHY information
- Channel BER/PER statistics
- ARQ retransmissions
- Receiver decoding process
- End-to-end KPIs

Example KPIs:

```text
✓ BER
✓ Packet Error Rate
✓ Throughput
✓ Delay
✓ Link Efficiency
✓ CRC Validation
✓ SNR Margin
```

---

# Simulation Parameters

You can modify these parameters in the `main()` function:

```python
SNR_DB    = 15.0
LOSS_PROB = 0.05
FER_PROB  = 0.02
```

## Parameters

| Parameter | Description |
|---|---|
| SNR_DB | Signal-to-Noise Ratio |
| LOSS_PROB | Packet loss probability |
| FER_PROB | Frame error rate |

---

# Educational Value

This project is useful for learning:

- Computer Networks
- OSI Model
- IoT Communication
- Wireless Networking
- LoRa Technology
- MQTT Protocol
- Error Detection & Correction
- Routing Algorithms
- TCP/IP Architecture
- Network Simulation

---

# Applications

- Smart Cities
- Environmental Monitoring
- Industrial IoT
- Wireless Sensor Networks
- Academic Demonstrations
- Networking Education
- Embedded Systems Learning

---

# Future Improvements

Possible enhancements:

- Real MQTT Broker integration
- Real LoRaWAN stack
- GUI Dashboard
- Live sensor integration
- Machine learning for AQI prediction
- Real-time graph plotting
- Multi-node sensor simulation
- Web dashboard using Flask/Django

---

# Author

Developed as a complete educational simulation project for understanding IoT communication systems and the OSI networking model.

---

# License

This project is open-source and available under the MIT License.
