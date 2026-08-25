import React from 'react';

/**
 * Shows a LIVE (green) or SIM (gray) badge based on the stored deployment plan.
 * Pass moduleName matching the keys in module_statuses from the plan
 * (e.g. "CarbonClock", "IDLEhunter", "WaterWatch", "ThermalTrace", "LightSpeed").
 *
 * CarbonClock always shows LIVE regardless of profile.
 */
export default function LiveSimBadge({ moduleName }) {
  const isLive = React.useMemo(() => {
    if (moduleName === 'CarbonClock') return true; // always live per spec
    try {
      const raw = localStorage.getItem('greencore_facility_profile');
      if (!raw) return false;
      const profile = JSON.parse(raw);
      // Re-derive which modules are active now from stored profile.
      // We keep this simple: check if there's a plan stored, or derive from servers/switches.
      const servers = profile.server_vendors || [];
      const switches = profile.switch_vendors || [];
      const easyServers = ['Dell PowerEdge (iDRAC)', 'HPE ProLiant (iLO)', 'Supermicro', 'Whitebox / Custom built', 'Virtual machines only (no bare metal)'];
      const managedSwitches = ['Cisco Catalyst / Nexus', 'Arista', 'Juniper', 'HPE / Aruba'];

      if (moduleName === 'IDLEhunter') {
        return servers.some(v => easyServers.includes(v));
      }
      if (moduleName === 'LightSpeed') {
        return switches.some(v => managedSwitches.includes(v));
      }
      // ThermalTrace and WaterWatch always need hardware
      return false;
    } catch {
      return false;
    }
  }, [moduleName]);

  if (isLive) {
    return (
      <span
        title="Live data from your hardware"
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '5px',
          background: '#10b981',
          color: '#fff',
          fontSize: '11px',
          fontWeight: 700,
          fontFamily: 'monospace',
          padding: '2px 8px',
          borderRadius: '999px',
          letterSpacing: '0.05em',
          lineHeight: 1.6,
        }}
      >
        <span
          style={{
            width: 7,
            height: 7,
            borderRadius: '50%',
            background: '#fff',
            display: 'inline-block',
            boxShadow: '0 0 5px #fff',
          }}
        />
        LIVE
      </span>
    );
  }

  return (
    <span
      title="Simulated data — see your deployment plan to activate with real hardware"
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '5px',
        background: '#374151',
        color: '#9ca3af',
        fontSize: '11px',
        fontWeight: 700,
        fontFamily: 'monospace',
        padding: '2px 8px',
        borderRadius: '999px',
        letterSpacing: '0.05em',
        lineHeight: 1.6,
        cursor: 'help',
      }}
    >
      <span
        style={{
          width: 7,
          height: 7,
          borderRadius: '50%',
          background: '#9ca3af',
          display: 'inline-block',
        }}
      />
      SIM
    </span>
  );
}
