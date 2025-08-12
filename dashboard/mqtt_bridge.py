#!/usr/bin/env python3
"""
Meshtastic to MQTT Bridge Script with Auto-Recovery
Listens to Meshtastic packets and forwards them to MQTT
For DefCon 33 Ham Radio Village - Enhanced for reliability
"""

import json
import time
import logging
import threading
from datetime import datetime
import paho.mqtt.client as mqtt
import meshtastic
import meshtastic.serial_interface
from pubsub import pub
import signal
import sys
import os
import glob

# Configuration
MQTT_BROKER = "localhost"  # Change to your MQTT broker IP
MQTT_PORT = 1883
MQTT_TOPIC_PREFIX = "meshtastic"
SERIAL_PORT = "/dev/ttyUSB0"  # Change to match your Heltec V3 port (Windows: COM3, etc.)

# Connection monitoring
CONNECTION_TIMEOUT = 300  # 5 minutes without packets = reconnect
HEARTBEAT_INTERVAL = 60   # Check connection every minute
RECONNECT_DELAY = 10      # Wait 10 seconds between reconnection attempts
MAX_RECONNECT_ATTEMPTS = 5  # Try 5 times before longer delay

# Set up logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/meshtastic_bridge.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def safe_json_convert(obj):
    """Safely convert any object to JSON-serializable format"""
    if obj is None:
        return None
    elif isinstance(obj, (str, int, float, bool)):
        return obj
    elif isinstance(obj, (list, tuple)):
        return [safe_json_convert(item) for item in obj]
    elif isinstance(obj, dict):
        return {str(k): safe_json_convert(v) for k, v in obj.items()}
    elif hasattr(obj, '__dict__'):
        # Handle objects with attributes (like User objects)
        result = {}
        for attr_name in dir(obj):
            if not attr_name.startswith('_'):  # Skip private attributes
                try:
                    attr_value = getattr(obj, attr_name)
                    if not callable(attr_value):  # Skip methods
                        result[attr_name] = safe_json_convert(attr_value)
                except:
                    continue
        return result
    else:
        # Fallback: convert to string
        return str(obj)

class MeshtasticBridge:
    def __init__(self):
        self.mqtt_client = None
        self.meshtastic_interface = None
        self.node_info = {}
        self.message_count = 0
        self.last_packet_time = time.time()
        self.running = True
        self.reconnect_attempts = 0
        self.heartbeat_thread = None
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
    def signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False
        if self.heartbeat_thread:
            self.heartbeat_thread.join(timeout=5)
        self.cleanup()
        sys.exit(0)
        
    def setup_mqtt(self):
        """Initialize MQTT client with retry logic"""
        try:
            # Use the newer callback API version to avoid deprecation warning
            self.mqtt_client = mqtt.Client(client_id="meshtastic_bridge", callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
            self.mqtt_client.on_connect = self.on_mqtt_connect
            self.mqtt_client.on_disconnect = self.on_mqtt_disconnect
            self.mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
            self.mqtt_client.loop_start()
            logger.info("MQTT client connected")
            return True
        except Exception as e:
            # Fallback to older API if the new one isn't available
            try:
                logger.info("Trying legacy MQTT client API...")
                self.mqtt_client = mqtt.Client(client_id="meshtastic_bridge")
                self.mqtt_client.on_connect = self.on_mqtt_connect_legacy
                self.mqtt_client.on_disconnect = self.on_mqtt_disconnect_legacy
                self.mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
                self.mqtt_client.loop_start()
                logger.info("MQTT client connected (legacy API)")
                return True
            except Exception as e2:
                logger.error(f"Failed to connect to MQTT broker: {e2}")
                return False
            
    def on_mqtt_connect(self, client, userdata, flags, reason_code, properties=None):
        """MQTT connection callback (new API)"""
        if reason_code == 0:
            logger.info("Connected to MQTT broker")
            self.publish_status("bridge_status", "connected")
        else:
            logger.error(f"Failed to connect to MQTT broker with code {reason_code}")
            
    def on_mqtt_disconnect(self, client, userdata, disconnect_flags, reason_code, properties=None):
        """MQTT disconnection callback (new API)"""
        logger.warning(f"Disconnected from MQTT broker with code {reason_code}")
        self.publish_status("bridge_status", "mqtt_disconnected")
        
    def on_mqtt_connect_legacy(self, client, userdata, flags, rc):
        """MQTT connection callback (legacy API)"""
        if rc == 0:
            logger.info("Connected to MQTT broker")
            self.publish_status("bridge_status", "connected")
        else:
            logger.error(f"Failed to connect to MQTT broker with code {rc}")
            
    def on_mqtt_disconnect_legacy(self, client, userdata, rc):
        """MQTT disconnection callback (legacy API)"""
        logger.warning(f"Disconnected from MQTT broker with code {rc}")
        self.publish_status("bridge_status", "mqtt_disconnected")
    
    def setup_meshtastic(self):
        """Initialize Meshtastic interface with enhanced error handling"""
        try:
            logger.info(f"🔌 Connecting to Meshtastic device on {SERIAL_PORT}")
            
            # Close existing connection if any
            if self.meshtastic_interface:
                try:
                    self.meshtastic_interface.close()
                except:
                    pass
                self.meshtastic_interface = None
            
            # Create new connection with timeout
            self.meshtastic_interface = meshtastic.serial_interface.SerialInterface(
                SERIAL_PORT,
                debugOut=None,  # Disable debug output for cleaner logs
                connectNow=True
            )
            
            # Give it time to initialize
            time.sleep(2)
            
            # Subscribe to message events
            pub.subscribe(self.on_receive, "meshtastic.receive")
            pub.subscribe(self.on_connection, "meshtastic.connection.established")
            pub.subscribe(self.on_node_updated, "meshtastic.node.updated")
            
            # Test the connection and get initial node list
            if self.test_connection():
                logger.info(f"✅ Meshtastic interface connected successfully")
                
                # Try to get initial node information
                self.refresh_node_database()
                
                self.last_packet_time = time.time()
                self.reconnect_attempts = 0
                self.publish_status("meshtastic_status", "connected")
                return True
            else:
                logger.error("❌ Meshtastic connection test failed")
                return False
                
        except Exception as e:
            logger.error(f"❌ Failed to connect to Meshtastic device: {e}")
            self.publish_status("meshtastic_status", f"error: {str(e)}")
            return False
    
    def reconnect_meshtastic(self):
        """Reconnect to Meshtastic device with enhanced recovery"""
        self.reconnect_attempts += 1
        logger.info(f"🔄 Reconnecting to Meshtastic (attempt {self.reconnect_attempts})...")
        
        if self.reconnect_attempts <= MAX_RECONNECT_ATTEMPTS:
            # Try normal reconnection first
            if self.setup_meshtastic():
                logger.info("✅ Reconnection successful")
                return True
            else:
                logger.warning(f"❌ Reconnection attempt {self.reconnect_attempts} failed")
                time.sleep(RECONNECT_DELAY)
        else:
            # After max attempts, try advanced recovery
            logger.info(f"🔧 Attempting advanced recovery after {MAX_RECONNECT_ATTEMPTS} failed attempts...")
            if self.advanced_reconnect_sequence():
                logger.info("✅ Advanced recovery successful")
                return True
            else:
                logger.error("❌ Advanced recovery failed, waiting longer before retry...")
                self.reconnect_attempts = 0  # Reset counter
                time.sleep(60)  # Wait 1 minute before trying again
        
        return False
    
    def refresh_node_database(self):
        """Get current node information from the interface"""
        try:
            if self.meshtastic_interface and hasattr(self.meshtastic_interface, 'nodes'):
                nodes = self.meshtastic_interface.nodes
                logger.info(f"📋 Refreshing node database with {len(nodes)} nodes")
                
                for node_num, node in nodes.items():
                    # node_num might already be a string or an int, handle both cases
                    if isinstance(node_num, str):
                        node_id = node_num if node_num.startswith('!') else f"!{node_num}"
                    else:
                        node_id = f"!{node_num:08x}"
                    
                    user_info = node.get('user', {})
                    
                    if user_info:  # Only process nodes with user info
                        short_name = user_info.get('shortName', 'UNK')
                        long_name = user_info.get('longName', 'Unknown')
                        hw_model = user_info.get('hwModel', 'Unknown')
                        
                        self.update_node_name(node_id, short_name, long_name, hw_model)
                        
                        logger.info(f"   📱 {short_name} ({node_id}) - {hw_model}")
        except Exception as e:
            logger.error(f"Error refreshing node database: {e}")
    
    def test_connection(self):
        """Test if the Meshtastic connection is working"""
        try:
            if self.meshtastic_interface and hasattr(self.meshtastic_interface, 'nodes'):
                # Try to access node information as a connection test
                nodes = self.meshtastic_interface.nodes
                logger.info(f"Connection test passed - found {len(nodes)} nodes")
                return True
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
        return False
    
    def check_connection_health(self):
        """Check if we're still receiving packets"""
        current_time = time.time()
        time_since_last_packet = current_time - self.last_packet_time
        
        if time_since_last_packet > CONNECTION_TIMEOUT:
            logger.warning(f"No packets received for {time_since_last_packet:.1f} seconds, connection may be dead")
            self.publish_status("connection_health", f"stale_{int(time_since_last_packet)}s")
            return False
        else:
            logger.debug(f"Connection healthy - last packet {time_since_last_packet:.1f}s ago")
            self.publish_status("connection_health", "healthy")
            return True
    
    def heartbeat_monitor(self):
        """Background thread to monitor connection health"""
        logger.info("Starting connection monitor thread")
        while self.running:
            try:
                time.sleep(HEARTBEAT_INTERVAL)
                if not self.running:
                    break
                    
                if not self.check_connection_health():
                    logger.warning("Connection appears unhealthy, attempting reconnection")
                    self.reconnect_meshtastic()
                    
            except Exception as e:
                logger.error(f"Error in heartbeat monitor: {e}")
    
    def reset_usb_driver(self):
        """Reset the CP210x USB driver module"""
        try:
            logger.info("🔧 Attempting to reset CP210x USB driver...")
            
            # Check if the module is loaded
            result = os.system("lsmod | grep cp210x > /dev/null")
            if result != 0:
                logger.warning("CP210x module not currently loaded")
                return False
            
            # Remove the module
            logger.info("   Removing cp210x module...")
            result = os.system("sudo rmmod cp210x")
            if result != 0:
                logger.error("Failed to remove cp210x module")
                return False
            
            # Wait a moment for cleanup
            time.sleep(2)
            
            # Reload the module
            logger.info("   Reloading cp210x module...")
            result = os.system("sudo modprobe cp210x")
            if result != 0:
                logger.error("Failed to reload cp210x module")
                return False
            
            # Wait for device enumeration
            time.sleep(3)
            
            # Check if our serial port is back
            if os.path.exists(SERIAL_PORT):
                logger.info("✅ CP210x driver reset successful - device detected")
                return True
            else:
                logger.warning(f"⚠️ CP210x driver reset completed but {SERIAL_PORT} not found")
                # List available serial ports for debugging
                self.list_available_ports()
                return False
                
        except Exception as e:
            logger.error(f"Error resetting USB driver: {e}")
            return False
    
    def list_available_ports(self):
        """List available serial ports for debugging"""
        try:
            logger.info("🔍 Scanning for available serial ports...")
            import glob
            
            # Common serial port patterns
            patterns = ['/dev/ttyUSB*', '/dev/ttyACM*', '/dev/cu.usbserial*', '/dev/cu.SLAB_USBtoUART*']
            
            found_ports = []
            for pattern in patterns:
                found_ports.extend(glob.glob(pattern))
            
            if found_ports:
                logger.info(f"   Found ports: {', '.join(found_ports)}")
                
                # If we find a port and our configured port doesn't exist, suggest update
                if not os.path.exists(SERIAL_PORT) and found_ports:
                    logger.info(f"   💡 Consider updating SERIAL_PORT from {SERIAL_PORT} to {found_ports[0]}")
            else:
                logger.warning("   No serial ports found")
                
        except Exception as e:
            logger.error(f"Error listing serial ports: {e}")
    
    def advanced_reconnect_sequence(self):
        """Advanced reconnection with driver reset"""
        logger.info("🔄 Starting advanced reconnection sequence...")
        
        # Step 1: Try normal reconnection first
        logger.info("Step 1: Attempting normal reconnection...")
        if self.setup_meshtastic():
            logger.info("✅ Normal reconnection successful")
            return True
        
        # Step 2: Check if device exists
        logger.info("Step 2: Checking device availability...")
        if not os.path.exists(SERIAL_PORT):
            logger.warning(f"⚠️ Device {SERIAL_PORT} not found")
            self.list_available_ports()
            
            # Step 3: Reset USB driver
            logger.info("Step 3: Resetting USB driver...")
            if self.reset_usb_driver():
                # Step 4: Try reconnection after driver reset
                logger.info("Step 4: Attempting reconnection after driver reset...")
                time.sleep(2)  # Give device time to settle
                if self.setup_meshtastic():
                    logger.info("✅ Reconnection successful after driver reset")
                    return True
            else:
                logger.error("❌ Driver reset failed")
        else:
            logger.info("✅ Device exists, trying alternative approaches...")
            
            # Step 3: Reset USB driver anyway (might be in bad state)
            logger.info("Step 3: Resetting USB driver (device in bad state)...")
            if self.reset_usb_driver():
                logger.info("Step 4: Attempting reconnection after driver reset...")
                time.sleep(2)
                if self.setup_meshtastic():
                    logger.info("✅ Reconnection successful after driver reset")
                    return True
        
        logger.error("❌ Advanced reconnection sequence failed")
        return False
    
    def on_connection(self, interface, topic=pub.AUTO_TOPIC):
        """Handle Meshtastic connection events"""
        logger.info("Meshtastic connection established event received")
        self.publish_status("connection_event", "established")
        self.last_packet_time = time.time()
        
    def on_node_updated(self, interface, node, topic=pub.AUTO_TOPIC):
        """Handle node information updates"""
        try:
            self.last_packet_time = time.time()  # Update last activity time
            
            node_id = f"!{node['num']:08x}"
            user_info = node.get('user', {})
            
            # Extract user information with emoji support
            short_name = user_info.get('shortName', 'UNK')
            long_name = user_info.get('longName', 'Unknown')
            hw_model = user_info.get('hwModel', 'Unknown')
            
            node_data = {
                'node_id': node_id,
                'short_name': short_name,
                'long_name': long_name,
                'hw_model': hw_model,
                'last_heard': node.get('lastHeard', 0),
                'snr': node.get('snr', 0),
                'battery_level': node.get('deviceMetrics', {}).get('batteryLevel', 0),
                'voltage': node.get('deviceMetrics', {}).get('voltage', 0.0),
                'channel_utilization': node.get('deviceMetrics', {}).get('channelUtilization', 0.0),
                'air_util_tx': node.get('deviceMetrics', {}).get('airUtilTx', 0.0)
            }
            
            self.node_info[node_id] = node_data
            self.publish_node_info(node_data)
            
            # Use emoji in logging for better visibility
            display_name = short_name if short_name != 'UNK' else long_name
            logger.info(f"👤 Updated node: {display_name} ({node_id}) - {hw_model}")
            
        except Exception as e:
            logger.error(f"Error processing node update: {e}")
    
    def on_receive(self, packet, interface=None):
        """Handle received Meshtastic packets"""
        try:
            self.last_packet_time = time.time()  # Update last activity time
            self.message_count += 1
            
            # Extract basic packet info
            from_id = f"!{packet['from']:08x}"
            to_id = f"!{packet['to']:08x}"
            
            packet_data = {
                'timestamp': datetime.now().isoformat(),
                'message_count': self.message_count,
                'from_id': from_id,
                'to_id': to_id,
                'from_name': self.get_node_name(from_id),
                'to_name': self.get_node_name(to_id),
                'hop_limit': packet.get('hopLimit', 0),
                'hop_start': packet.get('hopStart', 0),
                'want_ack': packet.get('wantAck', False),
                'via_mqtt': packet.get('viaMqtt', False),
                'channel': packet.get('channel', 0),
                'rssi': packet.get('rxRssi', 0),
                'snr': packet.get('rxSnr', 0.0),
                'rx_time': packet.get('rxTime', 0)
            }
            
            # Process different packet types
            if 'decoded' in packet:
                decoded = packet['decoded']
                packet_data['port_num'] = decoded.get('portnum', 'UNKNOWN')
                
                # Text messages
                if decoded.get('portnum') == 'TEXT_MESSAGE_APP':
                    packet_data['message_type'] = 'text'
                    packet_data['text'] = decoded.get('text', '')
                    logger.info(f"📱 Text from {packet_data['from_name']}: {packet_data['text']}")
                    
                # Node info - extract user information
                elif decoded.get('portnum') == 'NODEINFO_APP':
                    packet_data['message_type'] = 'nodeinfo'
                    if 'user' in decoded:
                        # Use the safe_json_convert function to handle User objects
                        user_info_safe = safe_json_convert(decoded['user'])
                        packet_data['user_info'] = user_info_safe
                        
                        # Update our node database with the new info
                        short_name = user_info_safe.get('shortName', '')
                        long_name = user_info_safe.get('longName', '')
                        hw_model = user_info_safe.get('hwModel', '')
                        
                        self.update_node_name(from_id, short_name, long_name, hw_model)
                        
                        # Update packet data with the new name
                        packet_data['from_name'] = self.get_node_name(from_id)
                        
                    logger.info(f"ℹ️ Node info from {packet_data['from_name']}")
                    
                # Position data
                elif decoded.get('portnum') == 'POSITION_APP':
                    packet_data['message_type'] = 'position'
                    if 'position' in decoded:
                        pos = decoded['position']
                        packet_data['latitude'] = pos.get('latitude', 0) / 1e7
                        packet_data['longitude'] = pos.get('longitude', 0) / 1e7
                        packet_data['altitude'] = pos.get('altitude', 0)
                    logger.info(f"📍 Position from {packet_data['from_name']}")
                    
                # Telemetry data
                elif decoded.get('portnum') == 'TELEMETRY_APP':
                    packet_data['message_type'] = 'telemetry'
                    if 'telemetry' in decoded:
                        telemetry = decoded['telemetry']
                        if 'deviceMetrics' in telemetry:
                            metrics = telemetry['deviceMetrics']
                            packet_data['battery_level'] = metrics.get('batteryLevel', 0)
                            packet_data['voltage'] = metrics.get('voltage', 0.0)
                            packet_data['channel_utilization'] = metrics.get('channelUtilization', 0.0)
                            packet_data['air_util_tx'] = metrics.get('airUtilTx', 0.0)
                            
                            # Update our node info with telemetry data
                            if from_id in self.node_info:
                                self.node_info[from_id]['battery_level'] = packet_data['battery_level']
                                self.node_info[from_id]['voltage'] = packet_data['voltage']
                                self.node_info[from_id]['channel_utilization'] = packet_data['channel_utilization']
                                self.node_info[from_id]['air_util_tx'] = packet_data['air_util_tx']
                    
                    logger.debug(f"📊 Telemetry from {packet_data['from_name']}")
                    
                else:
                    packet_data['message_type'] = 'other'
                    packet_data['port_num'] = str(decoded.get('portnum', 'UNKNOWN'))
                    logger.debug(f"📦 Other packet from {packet_data['from_name']}: {packet_data['port_num']}")
            
            # Publish to MQTT using safe conversion
            self.publish_packet(packet_data)
            
        except Exception as e:
            logger.error(f"Error processing received packet: {e}")
    
    def get_node_name(self, node_id):
        """Get friendly name for a node ID with emoji support"""
        if node_id in self.node_info:
            short_name = self.node_info[node_id].get('short_name', '')
            long_name = self.node_info[node_id].get('long_name', '')
            
            # Prefer short name, fallback to long name, then node_id
            if short_name and short_name != 'UNK':
                return short_name
            elif long_name and long_name != 'Unknown':
                return long_name
            else:
                return node_id
        
        # For unknown nodes, try to make a friendlier display
        return self.make_friendly_node_id(node_id)
    
    def make_friendly_node_id(self, node_id):
        """Convert hex node ID to a more friendly format"""
        if node_id.startswith('!'):
            # Take last 4 characters of hex for shorter display
            short_hex = node_id[-4:].upper()
            return f"Node-{short_hex}"
        return node_id
    
    def update_node_name(self, node_id, short_name=None, long_name=None, hw_model=None):
        """Update node information when we learn more about it"""
        if node_id not in self.node_info:
            self.node_info[node_id] = {
                'node_id': node_id,
                'short_name': 'UNK',
                'long_name': 'Unknown',
                'hw_model': 'Unknown',
                'last_heard': 0,
                'snr': 0,
                'battery_level': 0,
                'voltage': 0.0,
                'channel_utilization': 0.0,
                'air_util_tx': 0.0
            }
        
        # Update with new information
        node_data = self.node_info[node_id]
        if short_name:
            node_data['short_name'] = str(short_name)  # Ensure it's a string
        if long_name:
            node_data['long_name'] = str(long_name)   # Ensure it's a string
        if hw_model:
            node_data['hw_model'] = str(hw_model)     # Ensure it's a string
        
        node_data['last_heard'] = int(time.time())
        
        # Publish updated node info
        self.publish_node_info(node_data)
        
        logger.info(f"Updated node {node_id}: short='{short_name}', long='{long_name}', hw='{hw_model}'")
    
    def publish_packet(self, packet_data):
        """Publish packet data to MQTT with proper JSON serialization"""
        try:
            if not self.mqtt_client:
                return
            
            # Use safe_json_convert to ensure everything is JSON serializable
            clean_packet = safe_json_convert(packet_data)
                
            topic = f"{MQTT_TOPIC_PREFIX}/packets"
            payload = json.dumps(clean_packet, ensure_ascii=False)
            self.mqtt_client.publish(topic, payload)
            
            # Also publish by message type
            msg_type = clean_packet.get('message_type', 'unknown')
            type_topic = f"{MQTT_TOPIC_PREFIX}/packets/{msg_type}"
            self.mqtt_client.publish(type_topic, payload)
            
        except Exception as e:
            logger.error(f"Error publishing packet to MQTT: {e}")
            # Log the problematic packet for debugging
            logger.debug(f"Problematic packet keys: {list(packet_data.keys())}")
            for key, value in packet_data.items():
                logger.debug(f"  {key}: {type(value)} = {value}")
    
    def publish_node_info(self, node_data):
        """Publish node information to MQTT with proper JSON serialization"""
        try:
            if not self.mqtt_client:
                return
            
            # Use safe_json_convert to ensure everything is JSON serializable
            clean_node_data = safe_json_convert(node_data)
                
            topic = f"{MQTT_TOPIC_PREFIX}/nodes/{clean_node_data['node_id']}"
            payload = json.dumps(clean_node_data, ensure_ascii=False)
            self.mqtt_client.publish(topic, payload, retain=True)
            
            # Publish summary of all nodes
            nodes_summary = {
                'total_nodes': len(self.node_info),
                'nodes': []
            }
            
            # Clean node info for summary using safe_json_convert
            for node_data in self.node_info.values():
                clean_node = safe_json_convert(node_data)
                nodes_summary['nodes'].append(clean_node)
            
            nodes_summary['updated'] = datetime.now().isoformat()
            
            summary_topic = f"{MQTT_TOPIC_PREFIX}/nodes_summary"
            self.mqtt_client.publish(summary_topic, json.dumps(nodes_summary, ensure_ascii=False))
            
        except Exception as e:
            logger.error(f"Error publishing node info to MQTT: {e}")
    
    def publish_status(self, status_type, value):
        """Publish system status to MQTT with proper JSON serialization"""
        try:
            if not self.mqtt_client:
                return
            
            # Use safe_json_convert to ensure everything is JSON serializable
            safe_value = safe_json_convert(value)
                
            status_data = {
                'status_type': status_type,
                'value': safe_value,
                'timestamp': datetime.now().isoformat(),
                'message_count': self.message_count,
                'uptime': time.time() - self.start_time if hasattr(self, 'start_time') else 0
            }
            topic = f"{MQTT_TOPIC_PREFIX}/bridge_status"
            payload = json.dumps(status_data, ensure_ascii=False)
            self.mqtt_client.publish(topic, payload)
            
        except Exception as e:
            logger.error(f"Error publishing status to MQTT: {e}")
    
    def run(self):
        """Main run loop with robust error handling"""
        try:
            self.start_time = time.time()
            logger.info("Starting Meshtastic to MQTT bridge with auto-recovery")
            
            # Setup connections
            if not self.setup_mqtt():
                logger.error("Failed to setup MQTT, exiting")
                return False
                
            time.sleep(2)  # Give MQTT time to connect
            
            if not self.setup_meshtastic():
                logger.error("Failed to setup Meshtastic connection")
                # Don't exit, keep trying in heartbeat
            
            # Start heartbeat monitor
            self.heartbeat_thread = threading.Thread(target=self.heartbeat_monitor, daemon=True)
            self.heartbeat_thread.start()
            
            logger.info("Bridge started successfully. Monitoring connections...")
            
            # Keep the script running
            while self.running:
                time.sleep(1)
                
                # Publish periodic status
                if self.message_count % 100 == 0 and self.message_count > 0:
                    self.publish_status("periodic_update", {"packets": self.message_count, "uptime": time.time() - self.start_time})
                
        except KeyboardInterrupt:
            logger.info("Shutting down due to keyboard interrupt...")
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
        finally:
            self.running = False
            self.cleanup()
    
    def cleanup(self):
        """Clean up connections"""
        try:
            logger.info("Cleaning up connections...")
            self.running = False
            
            if self.meshtastic_interface:
                try:
                    self.meshtastic_interface.close()
                    logger.info("Meshtastic interface closed")
                except Exception as e:
                    logger.error(f"Error closing Meshtastic interface: {e}")
                    
            if self.mqtt_client:
                try:
                    self.publish_status("bridge_status", "disconnecting")
                    self.mqtt_client.loop_stop()
                    self.mqtt_client.disconnect()
                    logger.info("MQTT client disconnected")
                except Exception as e:
                    logger.error(f"Error disconnecting MQTT client: {e}")
                    
            logger.info("Cleanup completed")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

if __name__ == "__main__":
    bridge = MeshtasticBridge()
    bridge.run()