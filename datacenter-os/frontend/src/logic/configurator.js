import { EQUIPMENT_CATALOG } from '../data/equipmentCatalog';

// Monthly bill midpoints for ROI calculation
const BILL_MIDPOINTS = {
  'Under ₹1L': 75000,
  '₹1–5L': 300000,
  '₹5–20L': 1250000,
  '₹20L+': 3000000,
};

// Server count midpoints for ROI
const SERVER_COUNT_MIDPOINTS = {
  'Under 20': 10,
  '20–100': 60,
  '100–500': 300,
  '500+': 750,
};

// Budget tier: which numeric threshold to use for hardware
const BUDGET_VALUE = {
  'Under ₹50,000': 49999,
  '₹50,000 – ₹2,00,000': 200000,
  '₹2,00,000 – ₹10,00,000': 1000000,
  '₹10,00,000+': 9999999,
  'Not sure yet': 49999, // default to lowest
};

function getMonthlyBill(profile) {
  return BILL_MIDPOINTS[profile.electricity_bill] || 75000;
}

function getServerCount(profile) {
  return SERVER_COUNT_MIDPOINTS[profile.server_count] || 10;
}

function getBudgetValue(profile) {
  return BUDGET_VALUE[profile.budget] || 49999;
}

// Determine IDLEhunter status based on server vendors
function getIdleHunterStatus(profile) {
  const vendors = profile.server_vendors || [];
  const easyVendors = ['Dell PowerEdge (iDRAC)', 'HPE ProLiant (iLO)', 'Supermicro', 'Whitebox / Custom built', 'Virtual machines only (no bare metal)'];
  const hasEasyVendor = vendors.some(v => easyVendors.includes(v));
  const onlyCiscoOrDontKnow = vendors.length > 0 && vendors.every(v => v === 'Cisco UCS' || v === "Don't know");

  if (hasEasyVendor) {
    return { status: 'active_now', label: 'Active Now — Uses Existing Hardware', note: 'Server management APIs built in.' };
  }
  if (onlyCiscoOrDontKnow) {
    return { status: 'needs_setup', label: 'Requires Agent Install — 30 min setup', note: 'Install lightweight GreenCore agent on management host.' };
  }
  return { status: 'needs_setup', label: 'Requires Agent Install — 30 min setup', note: 'Install lightweight GreenCore agent on management host.' };
}

// Determine LightSpeed status based on switch vendors
function getLightSpeedStatus(profile) {
  const switches = profile.switch_vendors || [];
  const managedVendors = ['Cisco Catalyst / Nexus', 'Arista', 'Juniper', 'HPE / Aruba'];
  const hasManaged = switches.some(v => managedVendors.includes(v));
  const hasUnmanaged = switches.includes('Unmanaged switches only');
  const dontKnow = switches.includes("Don't know") || switches.length === 0;

  if (hasManaged) {
    return { status: 'active_now', label: 'Active Now — Enable SNMP (5 min config)', note: 'SNMP community string needed on your switch.' };
  }
  if (hasUnmanaged && !hasManaged) {
    return { status: 'phase1_hardware', label: `Requires ESP32 nodes — ₹700 total`, note: 'Use 2x ESP32 WiFi nodes for basic connectivity monitoring.' };
  }
  return { status: 'check', label: 'Check your switch model — likely SNMP capable', note: 'Most managed switches support SNMP v2c.' };
}

// Build Phase 1 hardware list based on budget
function buildPhase1Hardware(profile, monthlyBill, serverCount, budgetValue) {
  const items = [];
  let totalCost = 0;
  const modulesUnlocked = [];
  let projectedSavingsPerYear = 0;

  const sensors = EQUIPMENT_CATALOG.sensors;

  if (budgetValue < 50000) {
    // Budget tier: Under ₹50,000
    const qty_temp = 2;
    const tempItem = {
      name: sensors.temperature_basic.name,
      quantity: qty_temp,
      unit_cost: sensors.temperature_basic.cost,
      total_cost: qty_temp * sensors.temperature_basic.cost,
      where_to_buy: sensors.temperature_basic.where,
      what_it_unlocks: 'ThermalTrace (basic)',
      why_this_first: 'Cheapest way to detect hotspots before they cause downtime.'
    };
    items.push(tempItem);
    totalCost += tempItem.total_cost;
    modulesUnlocked.push('ThermalTrace');

    const flowItem = {
      name: sensors.flow_basic.name,
      quantity: 1,
      unit_cost: sensors.flow_basic.cost,
      total_cost: sensors.flow_basic.cost,
      where_to_buy: sensors.flow_basic.where,
      what_it_unlocks: 'WaterWatch (basic)',
      why_this_first: 'Entry-level cooling loop monitoring, no pipe cutting required.'
    };
    items.push(flowItem);
    totalCost += flowItem.total_cost;
    modulesUnlocked.push('WaterWatch');

    projectedSavingsPerYear = (monthlyBill * 0.08 + monthlyBill * 0.05) * 12;

  } else if (budgetValue < 200000) {
    // ₹50,000 – ₹2,00,000
    const qty_temp = 4;
    const tempItem = {
      name: sensors.temperature_basic.name,
      quantity: qty_temp,
      unit_cost: sensors.temperature_basic.cost,
      total_cost: qty_temp * sensors.temperature_basic.cost,
      where_to_buy: sensors.temperature_basic.where,
      what_it_unlocks: 'ThermalTrace (improved)',
      why_this_first: 'Cover more zones with affordable sensors.'
    };
    items.push(tempItem);
    totalCost += tempItem.total_cost;

    const rackSensorQty = 3;
    const rackItem = {
      name: sensors.temperature_rack.name,
      quantity: rackSensorQty,
      unit_cost: sensors.temperature_rack.cost,
      total_cost: rackSensorQty * sensors.temperature_rack.cost,
      where_to_buy: sensors.temperature_rack.where,
      what_it_unlocks: 'ThermalTrace (full rack monitoring with humidity)',
      why_this_first: 'Professional rack sensors for your 3 busiest racks.'
    };
    items.push(rackItem);
    totalCost += rackItem.total_cost;
    modulesUnlocked.push('ThermalTrace');

    const flowItem = {
      name: sensors.flow_industrial.name,
      quantity: 1,
      unit_cost: sensors.flow_industrial.cost,
      total_cost: sensors.flow_industrial.cost,
      where_to_buy: sensors.flow_industrial.where,
      what_it_unlocks: 'WaterWatch (full accuracy)',
      why_this_first: 'Clamp-on design requires no pipe cutting — install in minutes.'
    };
    items.push(flowItem);
    totalCost += flowItem.total_cost;
    modulesUnlocked.push('WaterWatch');

    projectedSavingsPerYear = (monthlyBill * 0.08 + monthlyBill * 0.05) * 12;

  } else {
    // ₹2,00,000+
    const rackCount = parseInt(profile.rack_count?.split('–')[0] || '10');
    const sensibleRackCount = isNaN(rackCount) ? 10 : Math.max(rackCount, 5);

    const rackItem = {
      name: sensors.temperature_rack.name,
      quantity: sensibleRackCount,
      unit_cost: sensors.temperature_rack.cost,
      total_cost: sensibleRackCount * sensors.temperature_rack.cost,
      where_to_buy: sensors.temperature_rack.where,
      what_it_unlocks: 'ThermalTrace (full rack mesh)',
      why_this_first: 'Full rack sensor mesh — complete thermal visibility across your facility.'
    };
    items.push(rackItem);
    totalCost += rackItem.total_cost;
    modulesUnlocked.push('ThermalTrace');

    const leakItem = {
      name: sensors.leak_detection.name,
      quantity: 2,
      unit_cost: sensors.leak_detection.cost,
      total_cost: 2 * sensors.leak_detection.cost,
      where_to_buy: sensors.leak_detection.where,
      what_it_unlocks: 'WaterWatch (leak detection zones)',
      why_this_first: 'Under-floor leak detection prevents catastrophic water damage.'
    };
    items.push(leakItem);
    totalCost += leakItem.total_cost;

    const flowItem = {
      name: sensors.flow_industrial.name,
      quantity: 1,
      unit_cost: sensors.flow_industrial.cost,
      total_cost: sensors.flow_industrial.cost,
      where_to_buy: sensors.flow_industrial.where,
      what_it_unlocks: 'WaterWatch (full flow accuracy)',
      why_this_first: 'Industrial-grade non-invasive flow meter.'
    };
    items.push(flowItem);
    totalCost += flowItem.total_cost;
    modulesUnlocked.push('WaterWatch');

    projectedSavingsPerYear = (monthlyBill * 0.08 + monthlyBill * 0.05) * 12;
  }

  return { items, totalCost, modulesUnlocked, projectedSavingsPerYear };
}

export function generateDeploymentPlan(profile) {
  const monthlyBill = getMonthlyBill(profile);
  const serverCount = getServerCount(profile);
  const budgetValue = getBudgetValue(profile);

  // --- Module statuses ---
  const idleHunterStatus = getIdleHunterStatus(profile);
  const lightSpeedStatus = getLightSpeedStatus(profile);

  const modulesActiveNow = ['CarbonClock'];
  if (idleHunterStatus.status === 'active_now') modulesActiveNow.push('IDLEhunter');
  if (lightSpeedStatus.status === 'active_now') modulesActiveNow.push('LightSpeed');

  const modulesNeedHardware = [];
  if (idleHunterStatus.status !== 'active_now') modulesNeedHardware.push('IDLEhunter');
  modulesNeedHardware.push('ThermalTrace', 'WaterWatch');
  if (lightSpeedStatus.status !== 'active_now') modulesNeedHardware.push('LightSpeed');

  // --- ROI ---
  const idleSavingsPerYear = serverCount * 0.15 * 200 * 24 * 30 * 8 / 1000 * 12;
  const thermalSavingsPerYear = monthlyBill * 0.08 * 12;
  const waterSavingsPerYear = monthlyBill * 0.05 * 12;
  const carbonSavingsPerYear = monthlyBill * 0.06 * 12;
  const totalAnnualSavings = idleSavingsPerYear + thermalSavingsPerYear + waterSavingsPerYear + carbonSavingsPerYear;

  // --- Phase 1 ---
  const phase1 = buildPhase1Hardware(profile, monthlyBill, serverCount, budgetValue);
  const paybackWeeks = phase1.totalCost > 0
    ? Math.round(phase1.totalCost / (totalAnnualSavings / 52))
    : 0;

  // Add IDLEhunter modules if active now
  if (idleHunterStatus.status === 'active_now') {
    phase1.modulesUnlocked.unshift('IDLEhunter');
  }

  // --- Architecture note ---
  const archNote = `GreenCore runs as a lightweight agent inside your management network. Your credentials and telemetry stay on-premise. Only anonymized benchmarking data is optionally shared with the GreenCore cloud for cross-facility comparison. You control what leaves your network.`;

  return {
    facility_name: profile.facility_name || 'Your Facility',
    module_statuses: {
      CarbonClock: { status: 'active_now', label: 'Active Now — No Hardware Required', note: 'Uses ElectricityMaps API only.' },
      IDLEhunter: { status: idleHunterStatus.status, label: idleHunterStatus.label, note: idleHunterStatus.note },
      LightSpeed: { status: lightSpeedStatus.status, label: lightSpeedStatus.label, note: lightSpeedStatus.note },
      ThermalTrace: { status: 'phase1_hardware', label: 'Unlocks in Phase 1', note: 'Requires temperature sensors.' },
      WaterWatch: { status: 'phase1_hardware', label: 'Unlocks in Phase 1', note: 'Requires flow sensor.' },
    },
    summary: {
      modules_active_now: modulesActiveNow,
      modules_need_hardware: modulesNeedHardware,
      estimated_annual_savings: Math.round(totalAnnualSavings),
      phase1_cost: phase1.totalCost,
      payback_weeks: paybackWeeks,
    },
    phases: [
      {
        phase_number: 1,
        title: 'Quick Wins — Thermal & Water Visibility',
        total_cost: phase1.totalCost,
        hardware_items: phase1.items,
        modules_unlocked: phase1.modulesUnlocked,
        projected_savings_per_year: Math.round(phase1.projectedSavingsPerYear),
        payback_weeks: paybackWeeks,
      },
      {
        phase_number: 2,
        title: 'Power & UPS Monitoring',
        total_cost: 18000,
        hardware_items: [
          {
            name: EQUIPMENT_CATALOG.sensors.ups_monitoring.name,
            quantity: 1,
            unit_cost: EQUIPMENT_CATALOG.sensors.ups_monitoring.cost,
            total_cost: EQUIPMENT_CATALOG.sensors.ups_monitoring.cost,
            where_to_buy: EQUIPMENT_CATALOG.sensors.ups_monitoring.where,
            what_it_unlocks: 'UPS health monitoring + battery health alerts',
            why_this_first: 'Prevent surprise outages from degraded UPS batteries.'
          }
        ],
        modules_unlocked: ['PowerWatch'],
        projected_savings_per_year: Math.round(monthlyBill * 0.03 * 12),
        payback_weeks: Math.round(18000 / (monthlyBill * 0.03 * 12 / 52)),
      },
      {
        phase_number: 3,
        title: 'Smart PDU Rollout',
        total_cost: 65000,
        hardware_items: [
          {
            name: EQUIPMENT_CATALOG.sensors.pdu_smart.name,
            quantity: 1,
            unit_cost: EQUIPMENT_CATALOG.sensors.pdu_smart.cost,
            total_cost: EQUIPMENT_CATALOG.sensors.pdu_smart.cost,
            where_to_buy: EQUIPMENT_CATALOG.sensors.pdu_smart.where,
            what_it_unlocks: 'Per-outlet power metering, remote switching, cabinet-level PUE',
            why_this_first: 'Complete the power visibility picture — identify energy hogs per outlet.'
          }
        ],
        modules_unlocked: ['PowerWatch (advanced)'],
        projected_savings_per_year: Math.round(monthlyBill * 0.04 * 12),
        payback_weeks: Math.round(65000 / (monthlyBill * 0.04 * 12 / 52)),
      }
    ],
    architecture_note: archNote,
    roadmap: [
      {
        title: 'Week 1–2: Install sensors, activate modules',
        description: 'Mount temperature & flow sensors. Connect to GreenCore agent. CarbonClock, IDLEhunter, and LightSpeed go live immediately.',
        when: 'Weeks 1–2'
      },
      {
        title: 'Month 2: Power visibility',
        description: 'Add UPS network management card. Begin tracking power trends and battery health. Set automated alerts.',
        when: 'Month 2'
      },
      {
        title: 'Quarter 2: Full automation',
        description: 'Smart PDU rollout for per-outlet metering. Enable automated workload deferral during peak carbon windows.',
        when: 'Q2'
      }
    ]
  };
}
