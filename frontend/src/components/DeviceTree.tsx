import { useState } from 'react';
import { ChevronRight, ChevronDown, Monitor, Server, Smartphone, Tv, Wifi, Circle } from 'lucide-react';

interface TreeNode {
    id: string;
    label: string;
    ip: string;
    mac: string;
    type: string;
    children: TreeNode[];
    status?: string;
}

const DeviceTree = ({ nodes, edges }: { nodes: any[], edges: any[] }) => {

    // Helper to build tree
    const buildTree = (): TreeNode[] => {
        // Map of id -> node
        const nodeMap: { [key: string]: TreeNode } = {};

        // Initialize all nodes
        nodes.forEach(n => {
            const data = n.data || {};
            nodeMap[n.id] = {
                id: n.id,
                label: data.label || n.id,
                ip: data.ip || '',
                mac: data.mac || '',
                type: data.type || n.type || 'Device',
                status: data.status,
                children: []
            };
        });

        // Identify children
        // Use a Set to track nodes that are targets (children)
        const childrenIds = new Set<string>();

        edges.forEach(e => {
            if (nodeMap[e.source] && nodeMap[e.target]) {
                nodeMap[e.source].children.push(nodeMap[e.target]);
                childrenIds.add(e.target);
            }
        });

        // Roots are nodes that are NOT targets of any edge
        // OR special case: "Cable Modem" if not strictly a root in specific graph logic (but here it usually is)
        const roots = Object.values(nodeMap).filter(n => !childrenIds.has(n.id));

        // Sort roots (Infrastructure first?)
        const infraOrder = ["Cable Modem", "Proxmox-Host", "OPNsense", "Main Switch"];

        // Helper to get index or default to end
        const getOrder = (label: string) => {
            const idx = infraOrder.findIndex(i => label.includes(i));
            return idx === -1 ? 999 : idx;
        }

        return roots.sort((a, b) => getOrder(a.label) - getOrder(b.label));
    };

    const treeData = buildTree();

    return (
        <div style={{ padding: '20px', color: '#e2e8f0' }}>
            <h2 style={{ marginBottom: '20px' }}>Network Directory</h2>
            <div style={{ border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', background: 'rgba(0,0,0,0.2)' }}>
                {treeData.map(node => (
                    <TreeItem key={node.id} node={node} level={0} />
                ))}
            </div>
        </div>
    );
};

const TreeItem = ({ node, level }: { node: TreeNode, level: number }) => {
    const [expanded, setExpanded] = useState(true); // Default open?
    const hasChildren = node.children.length > 0;

    // determine icon
    const getIcon = (type: string, label: string) => {
        const t = (type || '').toLowerCase();
        const l = (label || '').toLowerCase();

        if (t.includes('router') || l.includes('router') || l.includes('opnsense')) return <Wifi size={16} color="#fbbf24" />;
        if (t.includes('switch')) return <Server size={16} color="#60a5fa" />;
        if (t.includes('server') || t.includes('proxmox') || l.includes('modem')) return <Server size={16} color="#a855f7" />;
        if (t.includes('mobile') || t.includes('phone')) return <Smartphone size={16} color="#4ade80" />;
        if (t.includes('tv')) return <Tv size={16} color="#f472b6" />;
        return <Monitor size={16} color="#94a3b8" />;
    };

    return (
        <div style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
            <div
                style={{
                    display: 'flex',
                    alignItems: 'center',
                    padding: '8px 12px',
                    paddingLeft: `${level * 24 + 12}px`,
                    cursor: 'pointer',
                    background: expanded ? 'rgba(255,255,255,0.02)' : 'transparent',
                    transition: 'background 0.2s'
                }}
                onClick={() => setExpanded(!expanded)}
                className="tree-row"
            >
                <div style={{ width: '20px', display: 'flex', alignItems: 'center' }}>
                    {hasChildren && (
                        expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />
                    )}
                </div>

                <div style={{ marginRight: '10px' }}>
                    {getIcon(node.type, node.label)}
                </div>

                <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{ fontWeight: 500 }}>{node.label}</span>
                    {node.ip && <span style={{ fontSize: '12px', color: '#64748b', fontFamily: 'monospace' }}>{node.ip}</span>}
                </div>

                <div style={{ fontSize: '12px', color: '#64748b', minWidth: '120px', textAlign: 'right', display: 'flex', alignItems: 'center', gap: '6px', justifyContent: 'flex-end' }}>
                    {/* Status dot if available */}
                    {node.status && (
                        <Circle size={8} fill={node.status === 'running' ? '#4ade80' : '#94a3b8'} color="none" />
                    )}
                    <span>{node.type}</span>
                </div>
            </div>

            {expanded && hasChildren && (
                <div>
                    {node.children.map(child => (
                        <TreeItem key={child.id} node={child} level={level + 1} />
                    ))}
                </div>
            )}
        </div>
    );
};

export default DeviceTree;
