# DefCon 33 HRV Presentations
Presentations and other code that I presented at the Ham Radio Village for DefCon 33

## Meshtastic - Mesh Networking Made Easy
This presentation gives a brief introduction to Meshtastic, a mesh networking impelemntation using LoRa and LoRaWAN.
- [Keynote](./Presentations/Meshtastic%20-%20Mesh%20networking%20made%20easy.key)  
- [PDF](./Presentations/Meshtastic%20-%20Mesh%20networking%20made%20easy.pdf)

## Whats New in Digital Modes for 2025
This presentation is a companion to my presentation on digital modes that includes an update for 2025 of what's new in digital modes. Keynote. PDF.
- [Keynote](./Presentations/Meshtastic%20-%20Mesh%20networking%20made%20easy.key)  
- [PDF](./Presentations/Amateur%20Radio%20Digital%20Modes%20-%202025%20Update.pdf)

# Meshtastic Monitoring Station
The code for the meshtastic monitoring station is included [here](/dashboard). This monitoring station consists of multiple parts:
* Heltec V3 LoRaWAN Node - Flashed w/ DefCon firmware. Serial mode enabled
* Raspberry Pi 4b - Running Raspberry Pi OS
* MQTT - Message queueing server running in Raspberry Pi OS
* [Meshtastic Bridge Script](dashboard/mqtt_bridge.py) - Python script that listens to Meshtastic events received by the Heltec V3. Messages are populated in MQTT for display
* [Monitoring Dashboard HTML](dashboard/meshtastic_dashboard.html) - Status HTML page that connects to MQTT using a WebSocket and dsiplays messages populated by the bridge script
* Read the [README](dashboard/README.md) in the dashboard direcotry for full setup instructions

# Stand-alone Meshtastic Web Flasher
This builds a docker container that is a simple nginx webserver for running the Web Flasher offline when there is no internet access. This is helpful for environments where you are off-the-grid and don't have access to the internet, but need to flash nodes.
* Follow the [README](webflasher/README.md) instructions for getting this up and running

# Using these presentations
Please feel free to use these presentations as you see fit. Tweak them and present them at your own ham radio club, cybersecurity conference, book club, or anywhere else. An attribution would be nice, but not 100% required. Choose your own adventure.
