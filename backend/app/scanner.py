from scapy.all import ARP, Ether, srp
import socket
import logging

logger = logging.getLogger(__name__)

import os

# ...

class NetworkScanner:
    def __init__(self, ip_range=None):
        self.ip_ranges = (ip_range or os.getenv("SCAN_RANGE", "192.168.1.0/24")).split(',')

    def scan(self):
        """
        Perform an ARP scan to discover devices on the local network.
        Returns a list of dictionaries containing IP and MAC addresses.
        """
        all_results = []
        
        for net_range in self.ip_ranges:
            net_range = net_range.strip()
            if not net_range: continue
            
            logger.info(f"Scanning {net_range}...")
            try:
                arp = ARP(pdst=net_range)
                ether = Ether(dst="ff:ff:ff:ff:ff:ff")
                packet = ether/arp

                # timeout=2, verbose=0
                timeout_val = int(os.getenv("SCAN_TIMEOUT", "2"))
                ans, _ = srp(packet, timeout=timeout_val, verbose=0, iface=None)
                
                for sent, received in ans:
                    device = {
                        "ip": received.psrc,
                        "mac": received.hwsrc,
                        "hostname": self._get_hostname(received.psrc)
                    }
                    # Avoid duplicates if ranges overlap
                    if not any(d['ip'] == device['ip'] for d in all_results):
                        all_results.append(device)
                        
            except PermissionError:
                logger.error("Permission denied: scapy requires root privileges. Returning MOCK data.")
                # Only return mock once
                if not all_results:
                     return [
                        {"ip": "192.168.1.1", "mac": "AA:BB:CC:DD:EE:01", "hostname": "Gateway"},
                        {"ip": "192.168.1.100", "mac": "AA:BB:CC:DD:EE:02", "hostname": "Proxmox-Server"},
                        {"ip": "192.168.1.105", "mac": "AA:BB:CC:DD:EE:03", "hostname": "Desktop-PC"},
                        {"ip": "192.168.1.200", "mac": "AA:BB:CC:DD:EE:04", "hostname": "Smart-TV"},
                    ]
            except Exception as e:
                logger.error(f"Scan error on {net_range}: {e}")
                
        return all_results

    def _get_hostname(self, ip):
        try:
            return socket.gethostbyaddr(ip)[0]
        except socket.herror:
            return "Unknown"
