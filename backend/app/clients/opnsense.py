import requests
import urllib3
import os

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class OpnSenseClient:
    def __init__(self, host=None, api_key=None, api_secret=None, verify_ssl=False):
        self.host = host or os.getenv("OPNSENSE_HOST")
        self.key = api_key or os.getenv("OPNSENSE_KEY")
        self.secret = api_secret or os.getenv("OPNSENSE_SECRET")
        self.verify_ssl = verify_ssl
        self.base_url = f"https://{self.host}/api" if self.host else None

    def _get(self, endpoint):
        if not self.base_url or not self.key or not self.secret:
             return None
        try:
            response = requests.get(
                f"{self.base_url}/{endpoint}",
                auth=(self.key, self.secret),
                verify=self.verify_ssl,
                timeout=5
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            # print(f"Error fetching {endpoint}: {e}")
            return None

    def get_dhcp_leases(self):
        data = self._get("dhcpv4/leases/searchLease")
        if data:
            # print(f"DEBUG_DHCP: {data}")
            rows = data.get('rows', [])
            # Normalize description
            for row in rows:
                if 'descr' in row and row['descr']:
                    row['description'] = row['descr']
                elif 'description' not in row:
                    row['description'] = ''
            return rows
        return []

    def get_arp_table(self):
        # Trying multiple potential endpoints for ARP
        # 1. Diagnostics (most common for simple ARP dump)
        data = self._get("diagnostics/interface/getArp")
        if data:
            print(f"DEBUG_ARP_DIAG: found {len(data)} entries")
            return data
            
        # 2. Interface (sometimes here)
        data = self._get("interfaces/diagnostics/arp")
        if data:
             print(f"DEBUG_ARP_INT: found {len(data)} entries")
             return data
             
        print("DEBUG_ARP: No ARP data found")
        return []

    def get_status(self):
        # Check system status
        return {"status": "online" if self.base_url else "mock-online"}

    def get_alerts(self):
        # Fetch system status and convert to alerts
        if not self.base_url:
             return []
            
        alerts = []
        try:
            status_data = self._get("core/system/status")
            print(f"DEBUG_STATUS: {status_data}") # DEBUG
            
            # Example response: {"system": {"status": 0, "message": "OK"}}
            # Status: 0=OK, 1=Warning, 2=Error (approx)
            if status_data:
                # OPNsense system/status response is often wrapped in 'metadata'
                sys_status = status_data.get('metadata', {}).get('system', {})
                if not sys_status:
                     sys_status = status_data.get('system', {})
                
                code = sys_status.get('status')
                msg = sys_status.get('message', 'Unknown status')
                
                # Status 2 = "No pending messages" seems to be effectively OK/Green for OPNsense
                # We will only alert if code is 1 (Warning) or > 2 (Error) ?
                # Or just list it if it's not the standard "No pending messages"
                
                if code is not None and str(code) != "0" and str(code) != "2": 
                     alerts.append({
                        "severity": "warning" if str(code) == "1" else "error",
                        "message": f"OPNsense System: {msg}",
                        "timestamp": "Now"
                    })

        except Exception as e:
            print(f"Error fetching OPNsense alerts: {e}")
            pass
            
        return alerts

    def get_gateway_status(self):
        # Fetch gateway status to get WAN IP
        # endpoint: /api/routes/gateway/status
        status = self._get("routes/gateway/status")
        if status:
            return status
        return {}

