import { Handle, Position } from 'reactflow';
import { useState } from 'react';
import { Wifi, WifiOff, ChevronDown, ChevronRight, Server, Smartphone, Laptop, Tv, Printer, Camera } from 'lucide-react';

const DeviceNode = ({ data, id }: any) => {
    const [expanded, setExpanded] = useState(false);
    const [isWireless, setIsWireless] = useState(data.isWireless || false); // Sync with prop data

    // Icon select
    const getIcon = (type: string) => {
        const t = (type || '').toLowerCase();
        if (t.includes('server') || t.includes('proxmox') || t.includes('infrastructure')) return <Server size={16} />;
        if (t.includes('mobile') || t.includes('phone')) return <Smartphone size={16} />;
        if (t.includes('tv')) return <Tv size={16} />;
        if (t.includes('camera')) return <Camera size={16} />;
        if (t.includes('printer')) return <Printer size={16} />;
        return <Laptop size={16} />;
    };

    // Rollup toggle logic could go here (communicate with parent via context or props if needed)
    // For now, visual only as requested "unrolls to show ip..."

    // "Click to unroll"
    const toggleExpand = () => {
        setExpanded(!expanded);
    };

    const handleWirelessToggle = (e: any) => {
        e.stopPropagation();
        setIsWireless(!isWireless);
        // Ideally propagate this up to start a dashed line
        if (data.onWirelessToggle) data.onWirelessToggle(id, !isWireless);
    };

    // Check if node has children ( rollup indicator )
    // data.childCount passed from backend or calculated? 
    // Backend doesn't calculate it yet. Frontend can't easily know without graph context passed in data.
    // For now, let's assume if 'type' is infrastructure, it might have kids.

    return (
        <div
            onClick={toggleExpand}
            style={{
                padding: '10px',
                borderRadius: '8px',
                background: 'rgba(15, 23, 42, 0.9)',
                border: `1px solid ${expanded ? '#3b82f6' : 'rgba(255,255,255,0.1)'}`,
                minWidth: '150px',
                color: '#fff',
                fontSize: '12px',
                cursor: 'pointer',
                boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)'
            }}>
            <Handle type="target" position={Position.Top} style={{ background: '#555' }} />

            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <div style={{ color: '#94a3b8' }}>{getIcon(data.type)}</div>
                <div style={{ fontWeight: 500 }}>{data.label || 'Unnamed'}</div>
                {/* Rollup Indicator (Mock logic for now as we don't have child counts) */}
                {/* Rollup Indicator */}
                {(data.type === 'infrastructure' || data.type === 'Router' || data.type === 'Server') && (
                    <div
                        onClick={(e) => {
                            e.stopPropagation();
                            if (data.onToggleChildren) data.onToggleChildren(id);
                        }}
                        style={{ marginLeft: 'auto', background: '#334155', borderRadius: '50%', width: '16px', height: '16px', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '10px', cursor: 'pointer', zIndex: 10 }}>
                        +
                    </div>
                )}
            </div>

            {expanded && (
                <div style={{ marginTop: '10px', paddingTop: '10px', borderTop: '1px solid rgba(255,255,255,0.1)' }}>
                    <div style={{ marginBottom: '4px' }}>IP: <span style={{ fontFamily: 'monospace', color: '#cbd5e1' }}>{data.ip}</span></div>
                    <div style={{ marginBottom: '8px' }}>MAC: <span style={{ fontFamily: 'monospace', color: '#cbd5e1' }}>{data.mac}</span></div>

                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '8px' }}>
                        <span style={{ color: '#94a3b8' }}>Connection:</span>
                        <button
                            onClick={handleWirelessToggle}
                            style={{
                                display: 'flex', alignItems: 'center', gap: '4px',
                                background: 'none', border: 'none',
                                color: isWireless ? '#4ade80' : '#64748b',
                                cursor: 'pointer'
                            }}
                        >
                            {isWireless ? <Wifi size={14} /> : <WifiOff size={14} />}
                            {isWireless ? 'WiFi' : 'Wired'}
                        </button>
                    </div>
                </div>
            )}

            <Handle type="source" position={Position.Bottom} style={{ background: '#555' }} />
        </div>
    );
};

export default DeviceNode;
