# DefCon 33 Meshtastic Dashboard Setup Guide

## Overview
This setup creates a real-time monitoring dashboard for Meshtastic activity at the DefCon Ham Radio Village. The system captures packets from your Heltec V3 device and displays live network activity, node information, and message traffic.

## Prerequisites

### Hardware
- Raspberry Pi 4 or 5 with 4GB or more of RAM
- Raspberry Pi OS (64-bit) with desktop environment installed and configured
- Heltec V3 device running DefCon Meshtastic firmware
- USB cable to connect Heltec V3 to Raspberry Pi
- MicroSD card (32GB or larger recommended)
- Monitor/display for viewing the dashboard

### Software Requirements
```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install python3-venv python3-pip git chromium-browser fonts-noto-color-emoji -y

# Install MQTT broker (Mosquitto)
sudo apt install mosquitto mosquitto-clients -y

# Create Python virtual environment
python3 -m venv /home/pi/meshtastic-py
source /home/pi/meshtastic-py/bin/activate

# Install Python dependencies in virtual environment
pip install meshtastic paho-mqtt pubsub
```

## Step 1: Prepare Your Heltec V3

1. **Flash DefCon Firmware**: Ensure your Heltec V3 is running the DefCon Meshtastic firmware
2. **Connect via USB**: Connect the device to your computer
3. **Find Serial Port**:
   - Usually `/dev/ttyUSB0` or `/dev/ttyACM0`

```bash
# Check available ports
ls /dev/tty* | grep -E "(USB|ACM)"

# Add user to dialout group for serial port access
sudo usermod -a -G dialout pi

# Test connection (log out and back in first if you just added to dialout group)
python -c "import meshtastic.serial_interface; print('Connection test')"
```

## Step 2: Download the dashboard code

1. **Clone the GitHub repository**:
```bash
cd /home/pi
git clone https://github.com/jmarler/DefCon33HRVPresentations.git
```

2. **Create dashboard directory and copy files**:
```bash
mkdir -p /home/pi/meshtastic_dashboard
cd /home/pi/meshtastic_dashboard

# Copy dashboard files from the repository
cp /home/pi/DefCon33HRVPresentations/dashboard/mqtt_bridge.py .
cp /home/pi/DefCon33HRVPresentations/dashboard/meshtastic_dashboard.html .

# Download required JavaScript library
wget https://cdnjs.cloudflare.com/ajax/libs/paho-mqtt/1.0.1/mqttws31.min.js
```

## Step 3: Configure the Bridge Script

1. **Edit Configuration**: Update the mqtt_bridge.py script with your specific settings:
```python
# In the script, modify these lines:
MQTT_BROKER = "localhost"  # Change if MQTT broker is on different machine
SERIAL_PORT = "/dev/ttyUSB0"  # Change to match your Heltec V3 port
```

2. **Create Mosquitto WebSocket configuration**: Create the file `/etc/mosquitto/conf.d/websockets.conf`:
```bash
sudo cp /home/pi/DefCon33HRVPresentations/dashboard/websockets.conf /etc/mosquitto/conf.d/websockets.conf
```

3. **Create meshtastic-bridge systemd service**: Create the file `/etc/systemd/system/meshtastic-bridge.service`:
```bash
sudo cp /home/pi/DefCon33HRVPresentations/dashboard/meshtastic-bridge.service /etc/systemd/system/meshtastic-bridge.service
```

4. **Enable and start Mosquitto service**:
```bash
sudo systemctl enable mosquitto
sudo systemctl restart mosquitto
sudo systemctl status mosquitto
```

5. **Run the Bridge Script**: Start the meshtastic-bridge service and follow the logs (Press Ctrl-C to stop log following)
```bash
sudo systemctl daemon-reload
sudo systemctl enable meshtastic-bridge
sudo systemctl start meshtastic-bridge
sudo journalctl -u meshtastic-bridge -f
```

You should see output like:
```
Aug 11 19:23:24 meshpi python[2488]: 2025-08-11 19:23:24,114 - INFO - Starting Meshtastic to MQTT bridge with auto-recovery
Aug 11 19:23:24 meshpi python[2488]: 2025-08-11 19:23:24,117 - INFO - MQTT client connected
Aug 11 19:23:24 meshpi python[2488]: 2025-08-11 19:23:24,119 - INFO - Connected to MQTT broker
Aug 11 19:23:26 meshpi python[2488]: 2025-08-11 19:23:26,119 - INFO - 🔌 Connecting to Meshtastic device on /dev/ttyUSB0
Aug 11 19:23:34 meshpi python[2488]: 2025-08-11 19:23:34,996 - INFO - Connection test passed - found 2 nodes
Aug 11 19:23:34 meshpi python[2488]: 2025-08-11 19:23:34,996 - INFO - ✅ Meshtastic interface connected successfully
Aug 11 19:23:34 meshpi python[2488]: 2025-08-11 19:23:34,996 - INFO - 📋 Refreshing node database with 2 nodes
Aug 11 19:23:35 meshpi python[2488]: 2025-08-11 19:23:34,998 - INFO - Updated node !435905b8: short='05b8', long='Meshtastic 05b8', hw='HELTEC_V3'
Aug 11 19:23:35 meshpi python[2488]: 2025-08-11 19:23:35,001 - INFO -    📱 05b8 (!435905b8) - HELTEC_V3
Aug 11 19:23:35 meshpi python[2488]: 2025-08-11 19:23:35,006 - INFO - Updated node !bd4a358c: short='TDJM', long='Jons TDeck', hw='T_DECK'
Aug 11 19:23:35 meshpi python[2488]: 2025-08-11 19:23:35,008 - INFO -    📱 TDJM (!bd4a358c) - T_DECK
Aug 11 19:23:36 meshpi python[2488]: 2025-08-11 19:23:36,312 - INFO - Starting connection monitor thread
Aug 11 19:23:36 meshpi python[2488]: 2025-08-11 19:23:36,313 - INFO - Bridge started successfully. Monitoring connections...
```

## Step 5: Final Setup and Testing

1. **Reboot the Raspberry Pi** to ensure all changes take effect:
```bash
sudo reboot
```

2. **After reboot, verify everything is working**:
   - The desktop should automatically open Chromium in kiosk mode showing the dashboard
   - Check that services are running: `sudo systemctl status meshtastic-bridge mosquitto`
   - Verify the dashboard is receiving data from your Heltec V3

## Updating the Code

To get the latest updates from the repository:
```bash
cd /home/pi/DefCon33HRVPresentations
git pull
# Copy any updated files to your dashboard directory if needed
cp dashboard/mqtt_bridge.py /home/pi/meshtastic_dashboard/
cp dashboard/meshtastic_dashboard.html /home/pi/meshtastic_dashboard/
```

1. **Configure Chromium Browser to Autostart**: Create the autostart file:

```bash
mkdir -p /home/pi/.config/autostart
cp /home/pi/DefCon33HRVPresentations/dashboard/meshtastic-dashboard.desktop /home/pi/.config/autostart/
```

## Dashboard Features

### Recent Activity Panel
- Shows all recent Meshtastic packets in real-time
- Displays source, destination, message type, signal strength
- Automatically updates as new packets arrive

### Statistics Panel
- Packet type distribution (doughnut chart)
- Total packet counter
- Real-time statistics

### Active Nodes Panel
- Lists all discovered Meshtastic nodes
- Shows call signs, hardware models, battery levels
- Updates when nodes send telemetry

### Text Messages Panel
- Displays all text messages sent over the mesh
- Shows sender, message content, and signal quality
- Perfect for monitoring DefCon chat activity

### Telemetry Panel
- Battery level gauges for active nodes
- Signal strength charts over time
- Network health monitoring

## Troubleshooting

### Common Issues

**"Permission denied" on serial port**:
```bash
sudo usermod -a -G dialout $USER
# Log out and back in, or reboot
```

**Meshtastic connection fails**:
- Check USB cable connection
- Verify correct serial port in script
- Ensure Heltec V3 is not connected to another application
- Try different USB port

**MQTT connection issues**:
- Verify Mosquitto is running: `sudo systemctl status mosquitto`
- Check configuration: `sudo mosquitto_sub -h localhost -t "test"`
- Check firewall settings if accessing remotely
- Test with mosquitto client tools

**Python virtual environment issues**:
- Ensure virtual environment is activated: `source /home/pi/meshtastic-py/bin/activate`
- Verify packages installed: `pip list | grep meshtastic`
- Check Python path in systemd service matches your virtual environment

**Dashboard not loading**:
- Check that websockets.conf is loaded: `sudo systemctl restart mosquitto`
- Verify port 9001 is open: `sudo netstat -tlnp | grep 9001`
- Test WebSocket connection from browser developer tools

### Testing the Setup

1. **Test Mosquitto WebSocket**: Open browser to `http://localhost:9001` (should show "Upgrade Required" - this is normal)
2. **Generate test traffic**: Send a text message from another Meshtastic device
3. **Check logs**: Monitor the bridge script output
4. **Verify MQTT**: Use `mosquitto_sub -h localhost -t "meshtastic/#"` to see all traffic
5. **Dashboard activity**: Open the dashboard and confirm data appears

## DefCon Specific Configuration

### Ham Radio Village Setup
- Position your Heltec V3 antenna for best coverage of the village area
- Consider using an external antenna for better range
- Set appropriate channel for DefCon mesh network

### Network Optimization
- Monitor channel utilization in telemetry
- Adjust hop limits if needed for village coverage
- Consider multiple monitoring stations for redundancy

### Display Setup
- Use a large monitor/TV for the dashboard
- Consider fullscreen mode for public display
- Set up multiple dashboard views for different aspects

## Security Considerations

- This setup is for monitoring public Meshtastic traffic only
- No private/encrypted messages are captured or displayed
- All displayed data is already broadcast on the mesh network
- Suitable for ham radio demonstration and education

## Extending the Dashboard

### Additional Features You Can Add
- Geographic mapping of nodes (if position data available)
- Historical data logging and analysis
- Alert system for specific events
- Export functionality for data analysis
- Integration with other ham radio logging systems

### Custom Widgets
- Add custom gauges for specific metrics
- Create trend analysis charts
- Build custom alert panels
- Add sound notifications for events

## Performance Tips

- **For high traffic networks**: Increase MQTT buffer sizes
- **Multiple devices**: Use separate MQTT topics per device
- **Data retention**: Configure appropriate data retention periods
- **Resource usage**: Monitor CPU/memory usage during busy periods

## Support and Resources

- **Meshtastic Documentation**: [https://meshtastic.org/docs/](https://meshtastic.org/docs/)
- **DefCon Ham Radio Village**:[https://hamvillage.org](https://hamvillage.org)
- **MQTT Documentation**: [https://mqtt.org/](https://mqtt.org/)
- **Mosquitto Documentation**: [https://mosquitto.org/documentation/](https://mosquitto.org/documentation/)

## License and Credits

This setup is designed for educational and demonstration purposes at DefCon 33. Please respect the Ham Radio Village guidelines and FCC regulations when operating.

Have fun monitoring the mesh network! 🎯📡
