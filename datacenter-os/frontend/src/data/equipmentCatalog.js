export const EQUIPMENT_CATALOG = {
  servers: {
    "Dell PowerEdge (iDRAC)": {
      protocol: "Redfish",
      adapter: "ipmi_redfish",
      difficulty: "easy",
      cost_per_unit: 0,
      note: "iDRAC is built into all Dell PowerEdge servers — no additional hardware needed"
    },
    "HPE ProLiant (iLO)": {
      protocol: "Redfish / iLO REST API",
      adapter: "hpe_ilo",
      difficulty: "easy",
      cost_per_unit: 0,
      note: "iLO is built-in — enable network access in BIOS settings"
    },
    "Supermicro": {
      protocol: "IPMI v2.0 / Redfish",
      adapter: "ipmi_generic",
      difficulty: "easy",
      cost_per_unit: 0,
      note: "IPMI built-in on most Supermicro boards"
    },
    "Whitebox / Custom built": {
      protocol: "psutil agent",
      adapter: "psutil_local",
      difficulty: "easy",
      cost_per_unit: 0,
      note: "Install GreenCore lightweight agent — Python package, 5 min setup"
    },
    "Cisco UCS": {
      protocol: "UCS Manager XML API",
      adapter: "cisco_ucs",
      difficulty: "medium",
      cost_per_unit: 0,
      note: "Requires UCS Manager API credentials"
    },
    "Virtual machines only (no bare metal)": {
      protocol: "Hypervisor API",
      adapter: "vm_agent",
      difficulty: "easy",
      cost_per_unit: 0,
      note: "Lightweight agent installs on the hypervisor host"
    }
  },
  cooling: {
    "Liebert / Vertiv CRAC units": {
      protocol: "Modbus TCP / BACnet IP",
      adapter: "liebert_modbus",
      difficulty: "medium",
      cost_per_unit: 0,
      note: "Most Liebert units have built-in Modbus. Check model for port 502 availability"
    },
    "Schneider Electric CRAC units": {
      protocol: "BACnet IP / Modbus",
      adapter: "schneider_bacnet",
      difficulty: "medium",
      cost_per_unit: 0,
      note: "Requires EcoStruxure network module if not already networked"
    },
    "Airedale CRAH units": {
      protocol: "BACnet IP",
      adapter: "airedale_bacnet",
      difficulty: "medium",
      cost_per_unit: 0,
      note: "Airedale CRAH units support BACnet IP natively on most commercial models"
    },
    "In-row cooling units": {
      protocol: "Modbus RTU / BACnet",
      adapter: "inrow_modbus",
      difficulty: "medium",
      cost_per_unit: 0,
      note: "Check manufacturer documentation for RS-485 Modbus address map"
    },
    "Chiller plant": {
      protocol: "BACnet IP / Modbus TCP",
      adapter: "chiller_bacnet",
      difficulty: "hard",
      cost_per_unit: 0,
      note: "Typically requires on-site BMS integration — contact GreenCore professional services"
    },
    "Basic split AC units": {
      protocol: "No native protocol",
      adapter: "manual_entry",
      difficulty: "hard",
      cost_per_unit: 8000,
      note: "Recommend adding Sensaphone or equivalent monitoring gateway — ₹8,000"
    }
  },
  network: {
    "Cisco Catalyst / Nexus": {
      protocol: "SNMP v2c / gNMI",
      adapter: "cisco_snmp",
      difficulty: "easy",
      cost_per_unit: 0,
      note: "Enable SNMP community string in IOS. gNMI available on Nexus 9000+"
    },
    "Arista": {
      protocol: "gNMI / eAPI",
      adapter: "arista_gnmi",
      difficulty: "easy",
      cost_per_unit: 0,
      note: "Arista eAPI is REST-based — easiest switch integration available"
    },
    "Juniper": {
      protocol: "SNMP / Junos XML API",
      adapter: "juniper_snmp",
      difficulty: "easy",
      cost_per_unit: 0,
      note: "Enable SNMP on all interfaces. Junos XML API available on all modern devices"
    },
    "HPE / Aruba": {
      protocol: "SNMP / REST API",
      adapter: "aruba_rest",
      difficulty: "easy",
      cost_per_unit: 0,
      note: "Aruba CX switches have full REST API"
    },
    "Unmanaged switches only": {
      protocol: "No native protocol",
      adapter: "esp32_rssi",
      difficulty: "easy",
      cost_per_unit: 700,
      note: "Use ESP32 WiFi nodes for basic connectivity monitoring — ₹350 each, 2 minimum recommended"
    }
  },
  sensors: {
    temperature_basic: {
      name: "DS18B20 Waterproof Temp Probe + Pi",
      cost: 800,
      per: "per sensor",
      where: "Robu.in",
      unlocks: ["thermaltrace_basic"],
      note: "Most affordable thermal monitoring"
    },
    temperature_rack: {
      name: "Raritan DPX2-T1H1 Rack Sensor",
      cost: 8500,
      per: "per rack",
      where: "Raritan India / RS Components",
      unlocks: ["thermaltrace_full"],
      note: "Professional rack-mount with humidity"
    },
    flow_basic: {
      name: "YF-S201 Water Flow Sensor + Pi",
      cost: 500,
      per: "per loop",
      where: "Robu.in",
      unlocks: ["waterwatch_basic"],
      note: "Entry-level, suitable for demo/pilot"
    },
    flow_industrial: {
      name: "Keyence FD-Q Series Clamp-On Flow",
      cost: 45000,
      per: "per loop",
      where: "Keyence India",
      unlocks: ["waterwatch_full"],
      note: "Non-invasive clamp-on, no pipe cutting"
    },
    leak_detection: {
      name: "Dorlen Water Alert System",
      cost: 12000,
      per: "per zone",
      where: "Dorlen Products India",
      unlocks: ["waterwatch_leak"],
      note: "Under-floor leak detection cable"
    },
    ups_monitoring: {
      name: "APC Network Management Card",
      cost: 18000,
      per: "per UPS",
      where: "APC India",
      unlocks: ["powerwatch_ups"],
      note: "Adds SNMP + web monitoring to APC UPS"
    },
    pdu_smart: {
      name: "Raritan PX3 Smart PDU",
      cost: 65000,
      per: "per rack",
      where: "Raritan India",
      unlocks: ["powerwatch_pdu"],
      note: "Per-outlet power metering + remote switching"
    }
  }
};
