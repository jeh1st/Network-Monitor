import networkx as nx
import json

class NetworkGraph:
    def __init__(self):
        self.graph = nx.Graph()
        self.last_update = None

    def update_from_scan(self, devices):
        """
        Update the graph with devices found in the scan and specific user topology.
        """
        import datetime
        self.last_update = datetime.datetime.utcnow().isoformat()
        self.graph.clear() # Rebuild graph to ensure clean state with new rules
        
        # --- Defined Hardware MACs ---
        MAIN_SWITCH_MAC = "d8:07:b6:75:2f:f4"
        MAIN_ROUTER_MAC = "60:a4:b7:5c:5a:00"
        IOT_ROUTER_MAC = "e4:f4:c6:0b:33:1d"
        STREAMING_SWITCH_MAC = "54:07:7d:27:69:71"
        
        # --- Core Backbone Nodes ---
        # 1. Cable Modem (Public)
        self.graph.add_node("Cable Modem", label="Cable Modem", type='infrastructure', ip="Public IP")
        
        # 2. Proxmox Host
        self.graph.add_node("Proxmox-Host", label="Proxmox Host", type='infrastructure', ip="192.168.1.100") # Assume typical, will be updated by scan
        self.graph.add_edge("Cable Modem", "Proxmox-Host")
        
        # 3. OPNsense VM (Virtual Router inside Proxmox)
        self.graph.add_node("OPNsense", label="OPNsense VM", type='infrastructure', ip="192.168.1.1")
        self.graph.add_edge("Proxmox-Host", "OPNsense")
        
        # 4. Main Switch (Physical Heart)
        self.graph.add_node("Main Switch", label="Main Switch", type='infrastructure', mac=MAIN_SWITCH_MAC, ip="192.168.1.2")
        self.graph.add_edge("OPNsense", "Main Switch")
        
        # 5. Downstream Infrastructure
        self.graph.add_node("Main Router", label="Main Router", type='infrastructure', mac=MAIN_ROUTER_MAC, ip="192.168.1.3")
        self.graph.add_edge("Main Switch", "Main Router")
        
        self.graph.add_node("IoT Router", label="IoT Router", type='infrastructure', mac=IOT_ROUTER_MAC, ip="192.168.20.1")
        self.graph.add_edge("Main Switch", "IoT Router")
        
        self.graph.add_node("Streaming Switch", label="Streaming Switch", type='infrastructure', mac=STREAMING_SWITCH_MAC, ip="192.168.1.4")
        self.graph.add_edge("Main Switch", "Streaming Switch")


        # --- Device Placement Logic ---
        for device in devices:
            ip = device.get('ip', '')
            mac = device.get('mac', '').lower()
            hostname = device.get('hostname', 'Unknown')
            description = device.get('description', '')
            
            # Label logic: Description > Hostname > Unknown/Blank (but we need ID to select it)
            display_name = description if description else hostname
            if not display_name or display_name == 'Unknown':
                 # If truly unknown, maybe leave blank? User said "name will be left blank".
                 # But we need something to click on? Maybe just IP? 
                 # "if hostname is unavailable then the name will be left blank"
                 display_name = "" 
            
            # Skip infrastructure nodes already added manually (to avoid duplicates, though ID matching handles it)
            # We construct IDs based on IP or specific names for infra
            
            node_id = ip
            # Label is strictly the display name for now? UI will "unroll" to show IP/MAC.
            # But we need to pass IP/MAC in 'data', not burned into 'label' string for the UI to handle it cleanly.
            # Backend currently burns it into 'label'. We should change this to pass structured data.
            # However, for compat with existing 'default' nodes, we might keep label for now and add metadata.
            
            label = display_name if display_name else "(Unnamed)" # Placeholder so it isn't invisible? Or truly blank?
            if not display_name: label = " " # Space for blank?
            
            # Old logic included IP/MAC in label text. New requirement says "unroll to show".
            # So the visual label on the graph should JUST be the name.
            # We will store extra info in 'data' attributes for the frontend to use.
            
            # Identify Infrastructure IPs to update labels/IDs
            # PROXMOX HOST, SWITCHES, ROUTERS
            
            # Helper to update infra info if matched
            def update_infra(node_name, ip, mac):
                 if self.graph.has_node(node_name):
                     self.graph.nodes[node_name]['ip'] = ip
                     self.graph.nodes[node_name]['mac'] = mac
                     # Ensure label doesn't get messed up if it was manually set
                     # Actually, infra labels are set above (lines 25-47)
                     # We just want to ensure the data is there
                     pass

            if mac == MAIN_SWITCH_MAC:
                update_infra("Main Switch", ip, mac)
                continue 
            if mac == MAIN_ROUTER_MAC:
                update_infra("Main Router", ip, mac)
                continue
            if mac == IOT_ROUTER_MAC:
                update_infra("IoT Router", ip, mac)
                continue
            if mac == STREAMING_SWITCH_MAC:
                update_infra("Streaming Switch", ip, mac)
                continue
            
            # Special Case: Proxmox Host ?
            # If we see the Proxmox IP in the scan, update the Proxmox-Host node
            # PROXMOX_HOST from env might be the way, but scan is better as it has MAC.
            # We don't have Proxmox MAC in constants yet.
            # But we created Proxmox-Host manually.
            # If the IP matches env PROXMOX_HOST (ignoring port) -> update it.

            
            # Add ordinary device node
            # Determine type
            dtype = 'Device'
            h = hostname.lower()
            if "tv" in h or "shield" in h or "firestick" in h: dtype = 'Smart TV'
            elif "camera" in h or "cam" in h: dtype = 'Camera'
            elif "phone" in h or "pixel" in h or "iphone" in h: dtype = 'Mobile'
            elif "alexa" in h or "echo" in h or "google" in h: dtype = 'Voice Assistant'
            elif "printer" in h: dtype = 'Printer'
            elif "desktop" in h or "pc" in h or "laptop" in h or "macbook" in h: dtype = 'Computer'
            elif "proxmox" in h: dtype = 'Server'
            elif "opnsense" in h: dtype = 'Router'
            
            self.graph.add_node(node_id, label=label, mac=mac, type=dtype, ip=ip)
            
            # Connect to appropriate parent
            if ip.startswith("192.168.20.") or ip.startswith("192.168.30."):
                # Subnets .20 and .30 go to IoT Router
                # Exception: PoE Cameras on .30 hooked to Main Switch
                # We need a way to ID cameras. Keyword match?
                if "camera" in hostname.lower() or "cam" in hostname.lower():
                    self.graph.add_edge("Main Switch", node_id)
                else:
                    self.graph.add_edge("IoT Router", node_id)
            elif "tv" in hostname.lower() or "firestick" in hostname.lower() or "shield" in hostname.lower():
                # Streaming devices
                self.graph.add_edge("Streaming Switch", node_id)
            else:
                # Default .1.x devices go to Main Switch (or Main Router? User didn't specify distinct clients for Main Router)
                # "Main Switch ... feeds the rest of the network"
                self.graph.add_edge("Main Switch", node_id)

    def add_node_safe(self, node_id, **kwargs):
        """Helper to add/update node without losing existing data"""
        if self.graph.has_node(node_id):
            self.graph.nodes[node_id].update(kwargs)
        else:
            self.graph.add_node(node_id, **kwargs)

    def add_proxmox_resources(self, resources, arp_map=None):
        """
        Add Proxmox nodes, VMs, and LXCs to the graph to specific location.
        arp_map: dict of mac -> {ip, hostname} from scanner
        """
        arp_map = arp_map or {}
        
        for res in resources:
            name = res.get('name')
            res_type = res.get('type')
            status = res.get('status')
            vmid = res.get('id')
            mac = res.get('mac', '').lower()
            
            # Try to resolve IP from MAC
            ip = ""
            if mac and mac in arp_map:
                ip = arp_map[mac].get('ip', '')
            
            # Determine Label
            # Label logic: Description (if we had it) > Name
            # Proxmox resources typically just have a name
            display_name = name
            
            # Label should NOT contain IP/MAC anymore
            label = display_name
            
            node_data_attribs = {
                'label': label,
                'type': 'proxmox_resource',
                'status': status,
                'mac': mac,
                'ip': ip if ip else ""
            }

            if res_type == 'node':
                # The node is "Proxmox-Host".
                pass
            elif name == "OPNsense":
                # Already handled
                pass
            else:
                target_id = ip if ip else name
                
                # Check for existing node (merged from scan)
                if ip and self.graph.has_node(ip):
                    node_id = ip
                    # Update existing node
                    self.graph.nodes[node_id].update(node_data_attribs)
                    
                    # Ensure correct parentage (OPNsense)
                    for u, v in list(self.graph.edges(node_id)):
                        self.graph.remove_edge(u, v)
                    self.graph.add_edge("OPNsense", node_id)
                else:
                    # New node
                    self.graph.add_node(target_id, **node_data_attribs)
                    self.graph.add_edge("OPNsense", target_id)

    def get_react_flow_data(self):
        """
        Convert NetworkX graph to React Flow nodes and edges.
        """
        nodes = []
        edges = []
        
        # Simple layouting or let frontend handle it?
        # React Flow does not auto-layout by default without dagre/elk.
        # We will provide basic positions or let the frontend calculate.
        
        y_pos = 0
        x_pos = 0
        
        
        for node_id, data in self.graph.nodes(data=True):
            # Label is already formatted in update_from_scan or add_proxmox_resources
            # But wait, we just changed how label is constructed above for devices, 
            # BUT add_proxmox_resources still constructs full labels. We should fix that too if we want consistency.
            # For now, let's pass all the node attributes into 'data' so the Custom Node can render them.
            
            node_data = {
                "label": data.get('label', node_id),
                "ip": data.get('ip', ''), # We need to ensure these exist on the node
                "mac": data.get('mac', ''),
                "type": data.get('type', 'default'),
                "status": data.get('status', ''),
                # User asked for wireless toggle -> we need a state for it? 
                # Ideally, backend stores it if known, otherwise frontend handles it initially.
                # Let's assume we pass what we have.
            }
            
            # Extract IP/MAC from node attributes if not explicitly in 'data' dictionary earlier
            # networkx stores them as attributes on the node, accessible via `data` dict here.
            
            nodes.append({
                "id": node_id,
                "type": "deviceNode", # Use our new Custom Node type
                "data": node_data,
                "position": { "x": x_pos, "y": y_pos }
            })
            x_pos += 150
            if x_pos > 600:
                x_pos = 0
                y_pos += 100

        for u, v in self.graph.edges():
            edges.append({
                "id": f"e{u}-{v}",
                "source": u,
                "target": v
            })
            
        return {"nodes": nodes, "edges": edges, "last_update": self.last_update}

    def export_drawio_xml(self):
        # Todo: Implement MXGraph XML generation
        pass

    def get_alerts(self):
        """
        Generate alerts based on graph state (missing infrastructure, etc)
        """
        alerts = []
        # Check integrity of core backbone
        critical_nodes = ["Main Switch", "Main Router", "IoT Router", "OPNsense"]
        
        for node in critical_nodes:
            if not self.graph.has_node(node):
                alerts.append({
                    "severity": "error",
                    "message": f"Critical Infrastructure Missing: {node}",
                    "timestamp": self.last_update or "Now"
                })
            else:
                 pass
                 
        # Check for Unknown/New Devices (Intrusion Detection Lite)
        for node_id, data in self.graph.nodes(data=True):
            if data.get('type') == 'infrastructure': continue
            
            # Criteria for suspicious: Unknown hostname AND no Description
            label = data.get('label', '')
            hostname = data.get('hostname', '') # We might not have stored hostname on node directly, just label.
            # We better check how we store data.
            # In update_from_scan, we set 'label' to display_name.
            
            # If label is empty or "Unknown", flag it.
            if not label or "Unknown" in label or label.strip() == "":
                alerts.append({
                    "severity": "warning",
                    "message": f"Unknown Device Detected: {data.get('ip', 'No IP')}",
                    "timestamp": self.last_update or "Now"
                })
                 
        return alerts
