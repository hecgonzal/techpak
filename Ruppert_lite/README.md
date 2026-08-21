# Techpack System Architecture Specification

> Version 0.1 — Draft

## Overview

Techpack is a multi-device hub designed for inventory logging, health and environmental monitoring, and peripheral device power management. It is intended to operate as a compact, resilient ecosystem inside a backpack or wearable setup, with coordinated device services that share telemetry, logs, and user permissions across a network of connected hardware.

Ruppert-lite is a command-line shell built around AI-assisted tooling. It serializes and logs device data, provides a primary access path when a graphical interface is unavailable, and relies on logged information to improve recall and reduce hallucination in AI-driven interactions. Long-term integration with smart glasses may allow Ruppert-lite to interpret audio commands and visually identify objects for logging.

This document defines the boot architecture, service layout, runtime model, and security policies for the Techpack ecosystem.

## Table of Contents

- [Hardware and Boot Architecture](#hardware-and-boot-architecture)
- [System Architecture](#system-architecture)
- [Runtime and Applications](#runtime-and-applications)
- [Configuration and Policy Architecture](#configuration-and-policy-architecture)
- [Directory Structure](#directory-structure)

## Hardware and Boot Architecture

Techpack devices must wake from the following event types:

- Network events
- Sensor events
- User events

### Boot Order

```text
Firmware → Bootloader → Minimal Arch CoreOS → System Services → (Screen detected?) → System Services GUI → Runtime / Apps
```

### Minimal Arch CoreOS

The base operating environment is intentionally minimal and reproducible:

- Reproducible kernel configuration for x86/ARM
- Predictable device tree overlays
- No heavy desktop environment
- Only required packages installed

### Safe / Reset Mode

During recovery or restricted operation, the system boots with only logging and network controls active.

## System Architecture

### System Services (Lite, Network-Safe, Always-On)

These daemons form the Techpack OS layer and run on all devices unless restricted by device profile.

- `tp-sysinfo` — System telemetry aggregator
  - CPU load
  - Memory usage
  - Battery and thermal data
  - Uptime
  - Device capability flags
  - Wraps Linux primitives into a unified API

- `tp-netlink` — Network presence and device discovery
  - Broadcast device ID
  - Capability flags
  - Heartbeat
  - Mesh presence
  - Foundation for inter-device awareness

- `tp-msgbus` — Inter-device communication layer
  - Distributed IPC
  - Publish/subscribe channels
  - Command routing
  - Telemetry streaming
  - Backbone of Techpack communication

- `tp-authlite` — Lightweight identity and key exchange
  - Per-device identity keys
  - Session tokens
  - Capability-based permissions
  - Prevents impersonation and cross-device compromise

- `tp-packboard` — Sensor ingestion daemon
  - Packboard sensor data
  - Wearable telemetry
  - Environmental readings
  - Runs on wearable and packboard devices

- `tp-syncd` — State and file synchronization
  - Delta-based sync
  - Config propagation
  - Selective log sharing
  - rsync-lite optimized for Techpack

- `tp-ruppertlog` — Distributed logging backend
  - JSONL append
  - Schema registry
  - Log streaming
  - Backend for Ruppert-lite

- `tp-configd` — Configuration and policy enforcement
  - Device profiles
  - Runtime flags
  - Mode switching for low-power and lockout states
  - Central policy engine

- `tp-healthstats` — Health and fitness metrics engine
  - Hydration
  - Caloric burn
  - Sleep flags
  - Heart rate trends
  - Converts raw sensor data into meaningful metrics

- `tp-updater` — OTA updates for Techpack services
  - Version tracking
  - Patch deltas
  - Service restarts
  - Does not update the OS; only Techpack modules

### System Services GUI (Screen-Detected Only)

These services operate when a screen is available and provide a lower-power interface for devices that do not always run a full display stack.

- `tp-dashboard` — Unified UI for telemetry, packboard, health, and network
- `tp-notify` — Notification center and toast manager
- `tp-settings-ui` — Graphical configuration editor
- `tp-filebrowser` — Lightweight file navigator
- `tp-visualizer` — Charts, graphs, packboard maps, and health visualizations

## Runtime and Applications

### Ruppert-lite

Ruppert-lite is the primary CLI-based application interface for the Techpack ecosystem.

It acts as:

- A logger
- A data access point
- A query engine
- A historical metrics store
- A non-authoritative retrieval layer for logs and commands

This is the "Techpack brain" and is intended to retrieve and query data without acting as a source of authority over the system.

### Pacman Tools

The Pacman toolset includes:

- `techpack-tools`
- `techpack-services`
- `techpack-gui`

Any device may install these tools to participate in the broader ecosystem.

## Configuration and Policy Architecture

### Device Profiles

Device profiles determine:

- Hardware capabilities
- Service eligibility
- Job priority for Technet network services
- Power modes
- Sensor availability

Example profiles include:

- Workstation
- Brainboard
- Laptop
- Packboard
- Wearable
- Server
- Browse mode (GUI browser with adblocking and no persistent memory changes)
- Guest mode (unregistered device on the network)

### User Profiles

User profiles are synchronized across devices and define:

- User permissions
- Admin access
- GUI access
- Service-specific roles such as `authlite` user profile
- Ability to manage devices when connected to a screen

User profiles behave like Arch Linux user accounts with Techpack capability overlays.

### Local Logs

Each device maintains:

- System logs (journald)
- Techpack logs (`tp-ruppertlog`)
- Health logs (`tp-healthstats`)

Synchronization rules determine what data is shared across the network.

### Segregated Permissions Structure

The ecosystem uses a layered permissions model built on:

- Per-device identity keys
- Capability flags
- Profile-based restrictions
- Sandboxing via systemd and namespaces
- `tp-msgbus` ACLs

Example: a compromised wearable cannot modify workstation configurations or impersonate another device.

## Directory Structure

```text
techpack/
  docs/
    architecture.md
    services.md
    profiles.md
    security.md

  services/
    tp-sysinfo/
    tp-netlink/
    tp-msgbus/
    tp-authlite/
    tp-packboard/
    tp-syncd/
    tp-ruppertlog/
    tp-configd/
    tp-healthstats/
    tp-updater/

  services_gui/
    tp-dashboard/
    tp-notify/
    tp-settings-ui/
    tp-filebrowser/
    tp-visualizer/

  runtime/
    ruppert-lite/
    tools/
```

## Status

This project is currently in draft form and the architecture is still evolving as services and profiles are defined.

---

For additional context, see the active implementation files and project modules in this repository.
