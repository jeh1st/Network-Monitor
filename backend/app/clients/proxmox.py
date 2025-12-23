from proxmoxer import ProxmoxAPI
import os

class ProxmoxClient:
    def __init__(self, host=None, user=None, password=None, verify_ssl=False):
        self.host = host or os.getenv("PROXMOX_HOST")
        self.user = user or os.getenv("PROXMOX_USER")
        self.password = password or os.getenv("PROXMOX_PASSWORD")
        self.verify_ssl = verify_ssl
        self.proxmox = None
        
        if self.host and self.user and self.password:
            # Handle host:port format if present
            port = 8006
            if ":" in self.host:
                self.host, port_str = self.host.split(":")
                port = int(port_str)

            try:
                self.proxmox = ProxmoxAPI(
                    self.host, user=self.user, password=self.password, verify_ssl=self.verify_ssl, port=port
                )
            except Exception as e:
                print(f"Failed to connect to Proxmox: {e}")

    def get_nodes(self):
        if not self.proxmox:
            return [{"node": "pve-mock"}]
        try:
            return self.proxmox.nodes.get()
        except:
            return []

    def get_vms(self, node):
        if not self.proxmox:
            return [{"name": "mock-vm-1", "vmid": 100, "status": "running"}, {"name": "mock-opnsense", "vmid": 101, "status": "running"}]
        try:
            return self.proxmox.nodes(node).qemu.get()
        except:
            return []

    def get_lxcs(self, node):
        if not self.proxmox:
            return [{"name": "mock-lxc-1", "vmid": 200, "status": "running"}]
        try:
            return self.proxmox.nodes(node).lxc.get()
        except:
            return []

    def get_vm_config(self, node, vmid):
        try:
            return self.proxmox.nodes(node).qemu(vmid).config.get()
        except:
            return {}

    def get_lxc_config(self, node, vmid):
        try:
            return self.proxmox.nodes(node).lxc(vmid).config.get()
        except:
            return {}
    
    def get_all_resources(self):
        resources = []
        nodes = self.get_nodes()
        for node in nodes:
            node_name = node['node']
            # Add the node itself
            resources.append({"type": "node", "name": node_name, "id": node_name, "status": "online"})
            
            # VMs
            vms = self.get_vms(node_name)
            for vm in vms:
                vmid = vm.get('vmid')
                config = self.get_vm_config(node_name, vmid)
                # Parse MAC from net0 (e.g., "virtio=AA:BB:CC:...,bridge=vmbr0")
                mac = ""
                net0 = config.get('net0', '')
                # Parse MAC from net0. Format varies: "driver=MAC,bridge=..."
                # e.g. virtio=AA:BB.., or e1000=AA:BB..
                # We iterate parts and look for a MAC-like string
                if net0: 
                    parts = net0.split(',')
                    for p in parts:
                        if '=' in p:
                            val = p.split('=')[1]
                            if len(val) == 17 and ':' in val and val.count(':') == 5:
                                mac = val
                                break
                            
                resources.append({
                    "type": "qemu", 
                    "name": vm.get('name'), 
                    "id": vmid, 
                    "status": vm.get('status'), 
                    "parent": node_name,
                    "mac": mac
                })
            
            # LXCs
            lxcs = self.get_lxcs(node_name)
            for lxc in lxcs:
                vmid = lxc.get('vmid')
                config = self.get_lxc_config(node_name, vmid)
                # LXC net0: name=eth0,bridge=vmbr0,hwaddr=AA:BB:CC...
                mac = ""
                net0 = config.get('net0', '')
                if 'hwaddr=' in net0:
                    try:
                        mac = net0.split('hwaddr=')[1].split(',')[0]
                    except:
                        pass
                
                resources.append({
                    "type": "lxc", 
                    "name": lxc.get('name'), 
                    "id": vmid, 
                    "status": lxc.get('status'), 
                    "parent": node_name,
                    "mac": mac
                })
                
        return resources
