export const SETUP_INSTRUCTIONS = {
  "Dell PowerEdge (iDRAC)": {
    module: "PowerPrune",
    estimated_time: "15 minutes",
    difficulty: "Easy",
    prerequisites: [
      "iDRAC network port connected to management network",
      "iDRAC IP address assigned (check BIOS on boot → F2 → iDRAC settings)",
      "Admin credentials for iDRAC",
    ],
    steps: [
      {
        step: 1,
        title: "Enable Redfish API on iDRAC",
        detail:
          "Log into iDRAC web interface at http://[iDRAC-IP]. Go to iDRAC Settings → Services → Enable Redfish. Click Apply.",
        command: null,
        verify: "Navigate to http://[iDRAC-IP]/redfish/v1 — should return JSON",
      },
      {
        step: 2,
        title: "Create read-only monitoring user",
        detail:
          "In iDRAC → User Authentication → Add User. Username: verdegrid_monitor. Role: Read Only. This is safer than using admin credentials.",
        command: null,
        verify: null,
      },
      {
        step: 3,
        title: "Add server to VerdeGrid config",
        detail:
          "In your verdegrid-config.yaml, add this server under powerprune.hosts",
        command: `powerprune:
  adapter: ipmi_redfish
  hosts:
    - ip: 192.168.1.10
      username: verdegrid_monitor
      password: YOUR_PASSWORD`,
        verify:
          "VerdeGrid dashboard → PowerPrune → server appears in cluster grid with LIVE badge",
      },
    ],
  },

  "HPE ProLiant (iLO)": {
    module: "PowerPrune",
    estimated_time: "15 minutes",
    difficulty: "Easy",
    prerequisites: [
      "iLO management port connected to network",
      "iLO IP address known (check BIOS → System Utilities → iLO 5 Configuration Utility)",
      "iLO admin credentials",
    ],
    steps: [
      {
        step: 1,
        title: "Enable iLO REST API",
        detail:
          "Log into iLO web interface. Go to Administration → iLO Settings → Enable RESTful API. Save settings.",
        command: null,
        verify:
          "Visit https://[iLO-IP]/redfish/v1 — should return system info JSON",
      },
      {
        step: 2,
        title: "Create monitoring account",
        detail:
          "In iLO: Administration → User Administration → Add User. Username: verdegrid_ro. Assign 'Read Only' role.",
        command: null,
        verify: null,
      },
      {
        step: 3,
        title: "Add to VerdeGrid config",
        detail: "Update verdegrid-config.yaml under powerprune.hosts:",
        command: `powerprune:
  adapter: hpe_ilo
  hosts:
    - ip: 192.168.1.11
      username: verdegrid_ro
      password: YOUR_PASSWORD`,
        verify:
          "PowerPrune module shows the server with power and CPU data",
      },
    ],
  },

  "Supermicro (IPMI)": {
    module: "PowerPrune",
    estimated_time: "10 minutes",
    difficulty: "Easy",
    prerequisites: [
      "Supermicro IPMI port connected to management network",
      "IPMI IP address (check BIOS → IPMI Configuration)",
      "IPMI admin credentials",
    ],
    steps: [
      {
        step: 1,
        title: "Verify IPMI is accessible",
        detail:
          "From another machine on the same network, ping the IPMI IP and test the web interface at http://[IPMI-IP].",
        command: `# Test IPMI connectivity
ipmitool -I lanplus -H [IPMI-IP] -U admin -P PASSWORD chassis status`,
        verify: "Command returns 'System Power: on' or similar",
      },
      {
        step: 2,
        title: "Add to VerdeGrid config",
        detail: "Update verdegrid-config.yaml:",
        command: `powerprune:
  adapter: ipmi_generic
  hosts:
    - ip: 192.168.1.12
      username: admin
      password: YOUR_PASSWORD
      ipmi_version: 2.0`,
        verify: "PowerPrune shows sensor data for this server",
      },
    ],
  },

  "Whitebox / Custom built": {
    module: "PowerPrune + ThermOS",
    estimated_time: "20 minutes",
    difficulty: "Easy",
    prerequisites: [
      "Python 3.8+ installed on the server",
      "Server connected to management network",
      "SSH access to the server",
    ],
    steps: [
      {
        step: 1,
        title: "Install VerdeGrid psutil agent",
        detail: "SSH into the server and run:",
        command: `pip install verdegrid-agent psutil flask
python -m verdegrid_agent --port 5000 --node-id custom-server-1`,
        verify: "Visit http://[SERVER-IP]:5000/metrics — returns JSON with cpu_percent, ram_percent",
      },
      {
        step: 2,
        title: "Register as a service (optional)",
        detail:
          "To keep the agent running after reboot, create a systemd service:",
        command: `# /etc/systemd/system/verdegrid-agent.service
[Unit]
Description=VerdeGrid Monitoring Agent
After=network.target

[Service]
ExecStart=python -m verdegrid_agent --port 5000 --node-id custom-server-1
Restart=always

[Install]
WantedBy=multi-user.target`,
        verify: "sudo systemctl status verdegrid-agent shows Active: running",
      },
      {
        step: 3,
        title: "Add to VerdeGrid config",
        detail: "Update verdegrid-config.yaml:",
        command: `powerprune:
  adapter: psutil_local
  hosts:
    - ip: 192.168.1.20
      port: 5000
      node_id: custom-server-1`,
        verify: "PowerPrune shows this host with live CPU and memory metrics",
      },
    ],
  },

  "Raspberry Pi (psutil agent)": {
    module: "PowerPrune + ThermOS",
    estimated_time: "20 minutes",
    difficulty: "Easy",
    prerequisites: [
      "Raspberry Pi with Raspbian OS",
      "Python 3.8+ installed",
      "Pi connected to same network as VerdeGrid dashboard",
    ],
    steps: [
      {
        step: 1,
        title: "Install VerdeGrid agent",
        detail: "SSH into your Raspberry Pi and run:",
        command: `pip install flask psutil RPi.GPIO
pip install verdegrid-agent`,
        verify: null,
      },
      {
        step: 2,
        title: "Start the agent",
        detail:
          "Run the agent — it will automatically expose CPU, RAM, and temperature on port 5000:",
        command: `python -m verdegrid_agent \n  --port 5000 \n  --node-id pi-rack-1`,
        verify:
          "Open http://[Pi-IP]:5000/metrics in browser — should show JSON with cpu_percent, ram_percent, temperature",
      },
      {
        step: 3,
        title: "Connect DS18B20 temperature probe",
        detail:
          "Wire the DS18B20 sensor: Red → Pi Pin 1 (3.3V), Black → Pi Pin 6 (GND), Yellow → Pi Pin 7 (GPIO4). Add 4.7kΩ resistor between Red and Yellow.",
        command: `# Enable 1-Wire interface
echo "dtoverlay=w1-gpio" >> /boot/config.txt
sudo reboot`,
        verify:
          "ls /sys/bus/w1/devices/ — should show a 28-XXXX directory (sensor ID)",
      },
    ],
  },

  "ESP32 (network + thermal node)": {
    module: "NetPulse + ThermOS",
    estimated_time: "30 minutes",
    difficulty: "Medium",
    prerequisites: [
      "ESP32 development board",
      "DHT22 temperature sensor",
      "USB cable for flashing",
      "Thonny IDE installed on laptop",
    ],
    steps: [
      {
        step: 1,
        title: "Install MicroPython on ESP32",
        detail:
          "Download MicroPython firmware for ESP32 from micropython.org/download/esp32. Flash using esptool:",
        command: `pip install esptool
esptool.py --chip esp32 erase_flash
esptool.py --chip esp32 write_flash -z 0x1000 esp32-firmware.bin`,
        verify: "Open Thonny IDE → connect to ESP32 → REPL prompt appears",
      },
      {
        step: 2,
        title: "Wire DHT22 sensor",
        detail:
          "Connect DHT22 to ESP32: Pin 1 (VCC) → ESP32 3.3V, Pin 2 (DATA) → ESP32 GPIO4, Pin 4 (GND) → ESP32 GND. Add 10kΩ pull-up resistor between VCC and DATA.",
        command: null,
        verify: null,
      },
      {
        step: 3,
        title: "Flash VerdeGrid ESP32 firmware",
        detail:
          "Copy this MicroPython script to ESP32 as main.py. Update WIFI_SSID, WIFI_PASS, and WS_HOST:",
        command: `import network, time, ujson
from machine import Pin
import dht

WIFI_SSID = "YOUR_NETWORK"
WIFI_PASS = "YOUR_PASSWORD"
WS_HOST = "192.168.1.100"
NODE_ID = "esp32-rack-a"

sensor = dht.DHT22(Pin(4))
sta = network.WLAN(network.STA_IF)
sta.active(True)
sta.connect(WIFI_SSID, WIFI_PASS)

while not sta.isconnected():
    time.sleep(0.5)

while True:
    sensor.measure()
    rssi = sta.status('rssi')
    data = ujson.dumps({
        "node": NODE_ID,
        "temp": sensor.temperature(),
        "humidity": sensor.humidity(),
        "rssi": rssi
    })
    time.sleep(5)`,
        verify:
          "Thonny REPL shows 'Connected to WiFi' and prints sensor readings every 5 seconds",
      },
    ],
  },

  "YF-S201 Water Flow Sensor": {
    module: "CoolSense",
    estimated_time: "25 minutes",
    difficulty: "Medium",
    prerequisites: [
      "Raspberry Pi with GPIO access",
      "YF-S201 flow sensor",
      "Access to water pipe in cooling loop (inline install — must cut pipe or use T-fitting)",
    ],
    steps: [
      {
        step: 1,
        title: "Install sensor inline on pipe",
        detail:
          "The YF-S201 must be installed inline — cut the return water line and insert the sensor using compression fittings. Arrow on sensor body must point in direction of water flow.",
        command: null,
        verify:
          "Water flows through sensor — you can feel/hear the paddle wheel spinning inside",
      },
      {
        step: 2,
        title: "Wire to Raspberry Pi",
        detail:
          "Red wire → Pi 5V (Pin 2), Black wire → Pi GND (Pin 6), Yellow wire → Pi GPIO17 (Pin 11)",
        command: `# Test sensor reading
python3 -c "
import RPi.GPIO as GPIO
import time
GPIO.setmode(GPIO.BCM)
GPIO.setup(17, GPIO.IN, pull_up_down=GPIO.PUD_UP)
count = 0
def pulse(ch):
    global count
    count += 1
GPIO.add_event_detect(17, GPIO.FALLING, callback=pulse)
time.sleep(10)
lpm = (count / 7.5) / 10
print(f'Flow: {lpm:.2f} L/min')
GPIO.cleanup()
"`,
        verify: "Script prints a non-zero L/min value when water is flowing",
      },
    ],
  },

  "Cisco switch (SNMP)": {
    module: "NetPulse",
    estimated_time: "10 minutes",
    difficulty: "Easy",
    prerequisites: [
      "Cisco IOS switch on management network",
      "SSH access to switch",
      "Enable password",
    ],
    steps: [
      {
        step: 1,
        title: "Enable SNMP on Cisco switch",
        detail: "SSH into your switch and enter these commands in configuration mode:",
        command: `enable
configure terminal
snmp-server community verdegrid_ro RO
snmp-server location "Server Room 1"
snmp-server contact "ops@yourcompany.com"
end
write memory`,
        verify: `# Test from VerdeGrid server:
snmpwalk -v2c -c verdegrid_ro [SWITCH-IP] 1.3.6.1.2.1.2.2
# Should list all interfaces`,
      },
      {
        step: 2,
        title: "Add switch to VerdeGrid config",
        detail: "Update your verdegrid-config.yaml:",
        command: `netpulse:
  adapter: snmp_switch
  hosts:
    - ip: 192.168.1.1
      community: verdegrid_ro
      version: 2c`,
        verify:
          "VerdeGrid NetPulse module shows LIVE badge and real interface traffic",
      },
    ],
  },

  "APC UPS (Network Management Card)": {
    module: "PowerWatch",
    estimated_time: "20 minutes",
    difficulty: "Easy",
    prerequisites: [
      "APC UPS with Network Management Card (NMC) slot",
      "APC NMC card (AP9630 or AP9631 recommended)",
      "Network cable",
    ],
    steps: [
      {
        step: 1,
        title: "Install and configure NMC card",
        detail:
          "Power down UPS. Insert NMC card into management slot. Power on. Card will DHCP — find its IP in your router's DHCP table or use the APC Network Management Utility.",
        command: null,
        verify:
          "Visit http://[NMC-IP] — APC web interface loads with UPS status",
      },
      {
        step: 2,
        title: "Enable SNMP on the NMC",
        detail:
          "In APC web interface: Configuration → Network → SNMPv1. Set Community Name: verdegrid_ro. Access: Read Only. Apply.",
        command: null,
        verify: null,
      },
      {
        step: 3,
        title: "Add to VerdeGrid config",
        detail: "Update verdegrid-config.yaml:",
        command: `powerwatch:
  adapter: apc_snmp
  hosts:
    - ip: 192.168.1.50
      community: verdegrid_ro`,
        verify: "VerdeGrid shows UPS load %, battery %, and runtime remaining",
      },
    ],
  },

  "Liebert/Vertiv CRAC (Modbus)": {
    module: "ThermOS + CoolSense",
    estimated_time: "30 minutes",
    difficulty: "Medium",
    prerequisites: [
      "Liebert unit with Modbus TCP capability (check spec sheet — port 502)",
      "Unit's IP address on management network",
      "Liebert SiteNet or iCOM controller installed",
    ],
    steps: [
      {
        step: 1,
        title: "Verify Modbus TCP is enabled",
        detail:
          "On the Liebert iCOM controller: Main Menu → Communications → Modbus TCP. Ensure it shows Enabled and note the port (usually 502).",
        command: `# Test Modbus TCP connectivity from VerdeGrid server:
python3 -c "
from pymodbus.client import ModbusTcpClient
c = ModbusTcpClient('[LIEBERT-IP]', port=502)
c.connect()
result = c.read_holding_registers(0, 10, slave=1)
print(result.registers)
c.close()
"`,
        verify: "Script returns a list of register values (not an error)",
      },
      {
        step: 2,
        title: "Add to VerdeGrid config",
        detail:
          "Update verdegrid-config.yaml with register map. Common Liebert registers: 0x0001=supply air temp, 0x0002=return air temp, 0x0003=cooling capacity %",
        command: `thermos:
  adapters:
    - type: liebert_modbus
      ip: 192.168.1.60
      port: 502
      slave_id: 1
      register_map:
        supply_temp: 1
        return_temp: 2
        cooling_pct: 3`,
        verify: "ThermOS shows CRAC supply/return temperatures as LIVE",
      },
    ],
  },
};

// ─── Helper: get relevant instructions from a facility profile ────────────

export function getRelevantInstructions(facilityProfile) {
  const relevant = [];
  const servers = facilityProfile?.server_vendors || [];
  const cooling = facilityProfile?.cooling_equipment || [];
  const switches = facilityProfile?.switch_vendors || [];

  const serverMap = {
    'Dell PowerEdge (iDRAC)': 'Dell PowerEdge (iDRAC)',
    'HPE ProLiant (iLO)': 'HPE ProLiant (iLO)',
    'Supermicro': 'Supermicro (IPMI)',
    'Whitebox / Custom built': 'Whitebox / Custom built',
    'Virtual machines only (no bare metal)': 'Whitebox / Custom built',
  };
  const switchMap = {
    'Cisco Catalyst / Nexus': 'Cisco switch (SNMP)',
    'Unmanaged switches only': 'ESP32 (network + thermal node)',
  };
  const coolingMap = {
    'Liebert / Vertiv CRAC units': 'Liebert/Vertiv CRAC (Modbus)',
  };

  servers.forEach(v => { if (serverMap[v] && !relevant.includes(serverMap[v])) relevant.push(serverMap[v]); });
  switches.forEach(v => { if (switchMap[v] && !relevant.includes(switchMap[v])) relevant.push(switchMap[v]); });
  cooling.forEach(v => { if (coolingMap[v] && !relevant.includes(coolingMap[v])) relevant.push(coolingMap[v]); });

  return relevant;
}
