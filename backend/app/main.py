from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import requests
from app.clients.proxmox import ProxmoxClient
from app.clients.opnsense import OpnSenseClient
from app.scanner import NetworkScanner
from app.graph import NetworkGraph
from app.graph import NetworkGraph
from app.ai.local import LocalAI
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Network Monitor API")

# Allow requests from the frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global State
scanner = NetworkScanner()
proxmox_client = ProxmoxClient()
opnsense_client = OpnSenseClient()
net_graph = NetworkGraph()
local_ai = LocalAI()
last_notification_time = 0.0

@app.get("/")
def read_root():
    return {"status": "Network Monitor Backend Running"}

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/api/scan")
def trigger_scan(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_scan)
    return {"status": "Scan started in background"}

def run_scan():
    logger.info("Starting background network scan...")
    
    # 1. Network Scan
    devices = scanner.scan()
    
    # 2. OPNsense Data Enrichment
    try:
        # Fetch ARP Table - PRIMARY SOURCE for remote subnets
        arp_table = opnsense_client.get_arp_table() or []
        
        # Merge ARP data into devices
        # ARP table likely has: {"ip": "...", "mac": "...", "hostname": "...", "interface": "..."} or similar
        # We need to adapt it.
        for entry in arp_table:
            ip = entry.get('ip') or entry.get('address')
            mac = entry.get('mac')
            hostname = entry.get('hostname')
            
            if not ip or not mac: continue
            
            # Check if device already exists
            existing = next((d for d in devices if d['ip'] == ip), None)
            if existing:
                # Update MAC if missing (Scanner might miss MACs for remote subnets)
                if not existing.get('mac') and mac:
                    existing['mac'] = mac
                if existing.get('hostname') in ["Unknown", ""] and hostname:
                    existing['hostname'] = hostname
            else:
                # Add new device from ARP
                devices.append({
                    "ip": ip,
                    "mac": mac,
                    "hostname": hostname or "Unknown"
                })

        opn_leases = opnsense_client.get_dhcp_leases() or []
        
        # Enrich devices with DHCP data (Hostname, Description)
        # Create lookups
        lease_by_ip = {l['address']: l for l in opn_leases if 'address' in l}
        lease_by_mac = {l['mac'].lower(): l for l in opn_leases if 'mac' in l}
        
        for d in devices:
            # 1. Enrich existing devices
            if d['ip'] in lease_by_ip:
                lease = lease_by_ip[d['ip']]
                if d['hostname'] in ["Unknown", ""] and lease.get('hostname'):
                    d['hostname'] = lease.get('hostname')
                if not d.get('description'):
                    d['description'] = lease.get('description', '')
            
            # 2. Enrich by MAC if IP mismatch or missing ?
            if d.get('mac') and d['mac'] in lease_by_mac:
                 lease = lease_by_mac[d['mac']]
                 if not d.get('description'):
                    d['description'] = lease.get('description', '')

    except Exception as e:
        logger.error(f"Error fetching OPNsense data: {e}")

    net_graph.update_from_scan(devices)
    
    # Resolve Public IP (if possible)
    try:
        public_ip = requests.get('https://api.ipify.org', timeout=3).text
        if net_graph.graph.has_node("Cable Modem"):
             net_graph.graph.nodes["Cable Modem"]['ip'] = public_ip
    except Exception as e:
        logger.warning(f"Could not resolve public IP: {e}")
    
    # Create ARP/Lease Map for Proxmox Correlation
    # We want to find IP for a given MAC.
    # Priority: Scanned/ARP (Active) > DHCP Lease (Reserved/Recent)
    
    combined_lookup = {}
    
    # 1. Fill with DHCP first (lower priority, overwritten by active ARP)
    for l in opn_leases:
        if 'mac' in l and 'address' in l:
            combined_lookup[l['mac'].lower()] = {'ip': l['address'], 'hostname': l.get('hostname', '')}
            
    # 2. Overwrite with active devices from scan/ARP
    for d in devices:
        if 'mac' in d and 'ip' in d:
            combined_lookup[d['mac'].lower()] = d

    # 3. Proxmox Scan
    logger.info("Fetching Proxmox resources...")
    try:
        pmx_resources = proxmox_client.get_all_resources() or []
        net_graph.add_proxmox_resources(pmx_resources, arp_map=combined_lookup)
    except Exception as e:
        logger.error(f"Error fetching Proxmox data: {e}")
        
    logger.info(f"Scan cycle complete.")

@app.get("/api/graph")
def get_graph():
    return net_graph.get_react_flow_data()

@app.get("/api/alerts")
def get_alerts():
    alerts = []
    # 1. OPNsense System Alerts
    opn_alerts = opnsense_client.get_alerts()
    if opn_alerts:
        alerts.extend(opn_alerts)
        
    # 2. Graph/Infrastructure Alerts
    graph_alerts = net_graph.get_alerts()
    if graph_alerts:
        alerts.extend(graph_alerts)

    # 3. AI Analysis
    # We need to get the current devices list. 
    # Assuming net_graph has a way to provide the list of devices or we can get it from the graph.
    # For now, let's try to get it from net_graph if possible.
    try:
        # Extract devices from the graph nodes for analysis
        devices = []
        if hasattr(net_graph, 'graph'):
            for node_id, data in net_graph.graph.nodes(data=True):
               # convert node data back to device dict format if possible or just pass data
               devices.append(data)
        
        ai_alerts = local_ai.analyze(devices, opn_alerts)
        if ai_alerts:
            alerts.extend(ai_alerts)
    except Exception as e:
        logger.error(f"Error in AI analysis: {e}")
        
    # 3. Proxmox Connection Check
    # Quick check if we can reach nodes
    try:
        nodes = proxmox_client.get_nodes()
        if not nodes:
             alerts.append({"severity": "warning", "message": "Proxmox API unreachable or no nodes found", "timestamp": "Now"})
    except Exception as e:
         alerts.append({"severity": "error", "message": f"Proxmox Connection Error: {str(e)}", "timestamp": "Now"})

    # 4. Internet Connectivity (Check Public IP existence on Cable Modem node)
    if net_graph.graph.has_node("Cable Modem"):
        ip = net_graph.graph.nodes["Cable Modem"].get('ip')
        if not ip or ip == "Public IP" or ip == "Unknown":
             pass

    # Simple Notification dispatch (ntfy.sh)
    # To avoid spam, we check a global timestamp.
    # Note: Global state in a module works for single worker Uvicorn.
    global last_notification_time
    import time
    import os
    
    cutoff = time.time() - 600 # 10 minutes ago
    
    topic = os.getenv("NTFY_TOPIC")
    error_alerts = [a for a in alerts if a['severity'] == 'error']
    
    if topic and error_alerts:
        if last_notification_time < cutoff:
            try:
                # Summarize errors
                msg_body = "Errors detected:\n" + "\n".join([f"- {a['message']}" for a in error_alerts])
                
                requests.post(f"https://ntfy.sh/{topic}", 
                    data=msg_body,
                    headers={"Title": "NetMonitor Critical Alert", "Priority": "high", "Tags": "rotating_light"})
                last_notification_time = time.time()
                logger.info("Sent notification to ntfy.sh")
            except Exception as e:
                logger.error(f"Failed to send notification: {e}")

    return alerts

@app.post("/api/alerts/test-notify")
def test_notification():
    import os
    topic = os.getenv("NTFY_TOPIC")
    if not topic:
        return {"status": "error", "message": "NTFY_TOPIC not set in .env"}
    
    try:
        requests.post(f"https://ntfy.sh/{topic}", 
            data="This is a test notification from your Network Monitor.",
            headers={"Title": "NetMonitor Test", "Tags": "tada"})
        return {"status": "sent"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# --- Settings / Env Config ---
@app.get("/api/settings/env")
def get_env_config():
    # Read backend/.env file
    try:
        with open(".env", "r") as f:
            return {"content": f.read()}
    except FileNotFoundError:
         return {"content": ""}

from pydantic import BaseModel
class EnvConfig(BaseModel):
    content: str

@app.post("/api/settings/env")
def save_env_config(config: EnvConfig):
    try:
        with open(".env", "w") as f:
            f.write(config.content)
        return {"status": "saved"}
    except Exception as e:
         raise HTTPException(status_code=500, detail=str(e))

class GraphLayout(BaseModel):
    nodes: list
    edges: list

@app.post("/api/graph/save")
def save_graph_layout(layout: GraphLayout):
    # For now, we can save this to a json file 'layout.json'
    # And logic in graph.py could prioritize this layout if it exists?
    # Or we just save it for future features.
    try:
        with open("layout.json", "w") as f:
            f.write(layout.json())
        return {"status": "saved"}
    except Exception as e:
        logger.error(f"Error saving layout: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class ChatRequest(BaseModel):
    message: str

@app.post("/api/ai/chat")
def chat_with_ai(req: ChatRequest):
    # Gather context
    context = {}
    try:
        # Get graph data
        graph_data = net_graph.get_react_flow_data()
        
        # Simplify nodes for context to save tokens
        simple_nodes = []
        for node in graph_data.get('nodes', []):
            simple_nodes.append({
                "label": node.get('data', {}).get('label'),
                "ip": node.get('data', {}).get('ip'),
                "type": node.get('type')
            })
            
        context['nodes'] = simple_nodes
        context['node_count'] = len(simple_nodes)
        
    except Exception as e:
         logger.warning(f"Failed to gather context for AI: {e}")
         
    response = local_ai.chat(req.message, context)
    return {"response": response}

