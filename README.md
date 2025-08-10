# DefCon 33 HRV Presentations
Presentations and other code that I presented at the Ham Radio Village for DefCon 33

## Meshtastic - Mesh Networking Made Easy
This presentation goes a brief introduction to Meshtastic, a mesh networking impelemntation using LoRa and LoRaWAN.

## Whats New in Digital Modes for 2025
This presentation is a companion to my presentation on digital modes that includes an update for 2025 of what's new in digital modes.

# Meshtastic Monitoring Station
The code for the meshtastic monitoring station is included here. This monitoring station consists of multiple parts:
* Heltec V3 LoRaWAN Node - Flashed w/ DefCon firmware. Serial mode enabled
* Raspberry Pi 4b - Running Raspberry Pi OS
* MQTT - Message queueing server running in Raspberry Pi OS
* Meshtastic Bridge Script - Python script that listens to Meshtastic events received by the Heltec V3. Messages are populated in MQTT for display
* Monitoring Dashboard HTML - Status HTML page that connects to MQTT using a WebSocket and dsiplays messages populated by the bridge script
