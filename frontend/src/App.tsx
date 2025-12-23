import { useState, useEffect, useRef, useCallback } from 'react';
import { triggerScan, getGraphData, getAlerts } from './api';
import NetworkTopologyApi from './components/NetworkTopology';
import DeviceTree from './components/DeviceTree';
import './App.css';
import { Activity, ShieldCheck, Server, Search } from 'lucide-react';

const App = () => {
  const [isScanning, setIsScanning] = useState(false);
  const [nodes, setNodes] = useState([]);
  const [edges, setEdges] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [activeView, setActiveView] = useState('topology'); // 'dashboard', 'topology', 'devices', 'settings'
  const [editMode, setEditMode] = useState(false);

  // Hold the latest graph state from the child component
  const [currentLayout, setCurrentLayout] = useState({ nodes: [], edges: [] });
  const [lastScanTime, setLastScanTime] = useState<Date | null>(null);

  const saveLayout = async () => {
    console.log("Saving layout:", currentLayout);
    try {
      await fetch('http://localhost:8000/api/graph/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(currentLayout)
      });
      alert("Layout saved successfully!");
    } catch (e) {
      alert("Error saving layout: " + e);
    }
  }



  const loadData = async () => {
    const graphData = await getGraphData();
    setNodes(graphData.nodes);
    setEdges(graphData.edges);
    if (graphData.last_update) {
      setLastScanTime(new Date(graphData.last_update + 'Z')); // Ensure UTC
    }

    const alertsData = await getAlerts();
    setAlerts(alertsData);
  };

  const [scanDuration, setScanDuration] = useState(4000);

  useEffect(() => {
    loadData();
    const interval = setInterval(() => {
      getAlerts().then(setAlerts);
    }, 10000);

    // Fetch settings to determine scan duration
    fetch('http://localhost:8000/api/settings/env')
      .then(res => res.json())
      .then(data => {
        const lines = data.content.split('\n');
        let timeout = 2;
        let ranges = 1;
        lines.forEach((l: string) => { // explicit type for l
          if (l.startsWith('SCAN_TIMEOUT=')) timeout = parseInt(l.split('=')[1]) || 2;
          if (l.startsWith('SCAN_RANGE=')) ranges = l.split('=')[1].split(',').length || 1;
        });
        // Calculate duration: timeout * ranges * 1000 (ms) + 2000ms buffer
        // e.g. 2s * 3 ranges = 6s + 2s = 8000ms
        setScanDuration((timeout * ranges * 1000) + 2500);
      })
      .catch(e => console.error("Failed to load settings for duration Calc", e));

    return () => clearInterval(interval);
  }, []);

  const handleLayoutChange = useCallback((ns, es) => {
    setCurrentLayout({ nodes: ns, edges: es });
  }, []);

  const handleScan = async () => {
    setIsScanning(true);
    // Fire and forget: don't await the scan if it takes too long.
    try {
      triggerScan().catch(e => console.error("Background scan error:", e));
    } catch (e) {
      console.error("Scan init failed", e);
    }

    // Set a dynamic timeout based on complexity
    console.log(`Scan waiting for ${scanDuration}ms`);
    setTimeout(async () => {
      try {
        await loadData();
      } catch (e) {
        console.error("Post-scan load failed", e);
      } finally {
        setIsScanning(false);
      }
    }, scanDuration);
  };

  return (
    <div className="app-container">
      <header className="glass-header">
        <div className="logo">
          <Activity className="icon" />
          <h1>NetMonitor <span className="beta">AI</span></h1>
        </div>
        <div className="status-bar">
          <div className="status-item">
            <ShieldCheck size={16} color="#4ade80" />
            <span>System Secure</span>
          </div>
          <div className="status-item">
            <Server size={16} color="#60a5fa" />
            <span>Proxmox: Connected</span>
          </div>
        </div>
      </header>

      <main className="main-content">
        <aside className="sidebar glass-panel">
          <button className={`nav-btn ${activeView === 'dashboard' ? 'active' : ''}`} onClick={() => setActiveView('dashboard')}>Dashboard</button>
          <button className={`nav-btn ${activeView === 'topology' ? 'active' : ''}`} onClick={() => setActiveView('topology')}>Topology Map</button>
          <button className={`nav-btn ${activeView === 'devices' ? 'active' : ''}`} onClick={() => setActiveView('devices')}>Devices</button>
          <button className={`nav-btn ${activeView === 'settings' ? 'active' : ''}`} onClick={() => setActiveView('settings')}>Settings</button>

          <div className="actions">
            <button
              className={`action-btn ${isScanning ? 'scanning' : ''}`}
              onClick={handleScan}
              disabled={isScanning}
            >
              <Search size={18} />
              {isScanning ? 'Scanning...' : 'Scan Network'}
            </button>
          </div>
        </aside>

        <section className="visualization-area glass-panel">
          {/* Toolbar / Header for specific views */}
          <header style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            padding: '20px 30px',
            borderBottom: '1px solid rgba(255,255,255,0.05)'
          }}>
            <div>
              <h1 style={{ fontSize: '24px', fontWeight: '600' }}>Network Monitor</h1>
              <div style={{ fontSize: '12px', color: '#94a3b8', marginTop: '4px' }}>
                {isScanning ? 'Scanning network...' : `Last scan: ${lastScanTime ? lastScanTime.toLocaleTimeString() : 'Unknown'}`}
              </div>
            </div>
            <div style={{ display: 'flex', gap: '10px' }}>
              {activeView === 'topology' && (
                <>
                  <button
                    onClick={() => setEditMode(!editMode)}
                    className="action-btn"
                    style={{ background: editMode ? '#ca8a04' : '' }}
                  >
                    {editMode ? 'Done Editing' : 'Edit Graph'}
                  </button>
                  {editMode && <button onClick={() => saveLayout()} className="action-btn">Save Layout</button>}
                </>
              )}
              <button disabled={isScanning} onClick={handleScan} className="scan-btn">
                {isScanning ? 'Scanning...' : 'Scan Network'}
              </button>
            </div>
          </header>

          <section style={{ height: 'calc(100% - 140px)', position: 'relative' }}>
            {/* Topology View - Kept mounted to preserve state */}
            <div style={{ height: '100%', width: '100%', display: activeView === 'topology' ? 'block' : 'none' }}>
              <NetworkTopologyApi
                initialNodes={nodes}
                initialEdges={edges}
                isInteractive={editMode}
                onLayoutChange={handleLayoutChange}
              />
            </div>

            {/* Dashboard View */}
            <div style={{ padding: '30px', display: activeView === 'dashboard' ? 'block' : 'none' }}>
              <div className="stats-grid">
                {/* ... stats ... */}
                <div className="stat-card">
                  <h3>System Status</h3>
                  <div className="status-indicator status-good">
                    <span className="dot"></span>
                    Running
                  </div>
                </div>
                <div className="stat-card">
                  <h3>Devices Online</h3>
                  <div className="big-number">{nodes.filter((n: any) => n.data.label).length}</div>
                </div>
                <div className="stat-card">
                  <h3>Alerts</h3>
                  <div className="big-number error-text">{alerts.length}</div>
                </div>
              </div>

              <div style={{ marginTop: '30px' }}>
                <h3 style={{ marginBottom: '15px' }}>Live Alerts</h3>
                {alerts.length === 0 ? (
                  <div style={{ padding: '20px', background: 'rgba(255,255,255,0.02)', borderRadius: '12px', color: '#94a3b8' }}>
                    No active alerts
                  </div>
                ) : (
                  <ul className="alerts-list">
                    {alerts.map((a: any, i: number) => (
                      <li key={i} className={`alert-item ${a.severity}`}>
                        <span className="timestamp">{new Date(a.timestamp).toLocaleTimeString()}</span>
                        <span>{a.message}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>

            {/* Devices View */}
            <div style={{ padding: '0', overflow: 'auto', maxHeight: '100%', display: activeView === 'devices' ? 'block' : 'none' }}>
              <DeviceTree
                nodes={currentLayout.nodes.length > 0 ? currentLayout.nodes : nodes}
                edges={currentLayout.edges.length > 0 ? currentLayout.edges : edges}
              />
            </div>

            {/* Settings View */}
            <div style={{ height: '100%', display: activeView === 'settings' ? 'block' : 'none' }}>
              <SettingsView />
            </div>

          </section>
        </section>
      </main>
    </div>
  );
}

const SettingsView = () => {
  const [content, setContent] = useState('');
  const [status, setStatus] = useState('');
  const [parsedSections, setParsedSections] = useState<any>({});
  const [editingSection, setEditingSection] = useState<string | null>(null);

  // Simple parser for .env
  const parseEnv = (raw: string) => {
    const lines = raw.split('\n');
    const sections: any = { 'Global': [] };
    let currentSection = 'Global';

    lines.forEach(line => {
      if (line.trim().startsWith('# ---')) {
        currentSection = line.replace('# ---', '').replace('---', '').trim();
        sections[currentSection] = [];
      }
      sections[currentSection].push(line);
    });
    return sections;
  };

  const loadConfig = () => {
    fetch('http://localhost:8000/api/settings/env')
      .then(res => res.json())
      .then(data => {
        setContent(data.content);
        setParsedSections(parseEnv(data.content));
        setStatus('');
      })
      .catch(err => setStatus('Error loading config: ' + err.message));
  };

  useEffect(() => {
    loadConfig();
  }, []);

  const handleSaveSection = async (sectionName: string, newLines: string[]) => {
    // Reconstruct file
    let newContent = "";
    Object.keys(parsedSections).forEach(key => {
      if (key === sectionName) {
        // Ensure the section header is preserved if it's not 'Global'
        if (key !== 'Global' && !newLines[0].startsWith('# ---')) {
          newContent += `# --- ${key} ---\n`;
        }
        newContent += newLines.join('\n') + '\n';
      } else {
        // Preserve existing section headers
        if (key !== 'Global' && parsedSections[key].length > 0 && !parsedSections[key][0].startsWith('# ---')) {
          newContent += `# --- ${key} ---\n`;
        }
        newContent += parsedSections[key].join('\n') + '\n';
      }
    });

    // Save
    try {
      await fetch('http://localhost:8000/api/settings/env', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: newContent })
      });
      setStatus('Saved!');
      setContent(newContent);
      setParsedSections(parseEnv(newContent));
      setEditingSection(null);
      setTimeout(() => setStatus(''), 2000);
    } catch (e) {
      setStatus('Error saving');
    }
  };

  return (
    <div style={{ padding: '30px', height: '100%', overflow: 'auto' }}>
      <h2 style={{ marginBottom: '20px' }}>System Configuration</h2>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
        {Object.keys(parsedSections).map(section => (
          <div key={section} style={{ background: 'rgba(255,255,255,0.02)', padding: '20px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.05)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '10px' }}>
              <h3 style={{ textTransform: 'uppercase', fontSize: '14px', color: '#94a3b8' }}>{section}</h3>
              {editingSection !== section ? (
                <button onClick={() => setEditingSection(section)} className="action-btn" style={{ fontSize: '12px', padding: '4px 12px', width: 'auto' }}>Edit</button>
              ) : (
                <div style={{ display: 'flex', gap: '10px' }}>
                  <button onClick={() => setEditingSection(null)} className="action-btn" style={{ background: '#475569' }}>Cancel</button>
                  <button onClick={() => {
                    // Grab value from textarea ID below (quick hack for state)
                    const el = document.getElementById(`edit-${section}`) as HTMLTextAreaElement;
                    if (el) handleSaveSection(section, el.value.split('\n'));
                  }} className="action-btn">Save</button>
                </div>
              )}
            </div>

            {editingSection === section ? (
              <textarea
                id={`edit-${section}`}
                defaultValue={parsedSections[section].join('\n')}
                style={{
                  width: '100%', minHeight: '150px', background: '#020617',
                  color: '#e2e8f0', border: 'none', padding: '10px',
                  fontFamily: 'monospace', borderRadius: '4px'
                }}
              />
            ) : (
              <pre style={{ color: '#cbd5e1', fontSize: '13px', overflowX: 'auto' }}>
                {parsedSections[section].join('\n')}
              </pre>
            )}
          </div>
        ))}
      </div>
      {status && <div style={{ position: 'fixed', bottom: '20px', right: '20px', background: status.includes('Error') ? '#ef4444' : '#22c55e', padding: '10px 20px', borderRadius: '8px', color: '#fff', display: 'flex', alignItems: 'center', gap: '10px' }}>
        {status}
        {status.includes('Error') && <button onClick={loadConfig} style={{ background: 'white', color: 'black', border: 'none', borderRadius: '4px', padding: '4px 8px', cursor: 'pointer', fontWeight: 'bold' }}>Retry</button>}
      </div>}
    </div>
  );
};

export default App;
