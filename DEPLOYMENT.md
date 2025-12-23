# Network Monitor - Proxmox LXC Deployment Guide

This guide will help you install the Network Monitor in a Proxmox LXC container and set it up for easy updates.

## 1. Create the LXC Container
In your Proxmox web interface:
1. Click **"Create CT"**.
2. **Template**: Choose `ubuntu-24.04-standard` (or Debian 12).
3. **Resources**: 
   - 2-4 CPU Cores (important for scanning/python).
   - 2GB+ RAM.
4. **Network**: **CRITICAL** - Set the Bridge to `vmbr0` (or your main LAN bridge) and set IPv4 to `DHCP` or a `Static IP` on your main subnet (e.g., `192.168.1.55/24`). Do *not* use a separate firewalled bridge if you want accurate scanning.
5. Finish and Start the container.

## 2. Initial Setup
Open the Console of your new LXC:

```bash
# Update system
apt update && apt upgrade -y

# Install dependencies (Python, Node.js, Git, Nmap/Scapy requirements)
apt install -y python3 python3-pip python3-venv git curl libpcap-dev build-essential net-tools

# Install Node.js (Version 20+)
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt install -y nodejs
```

## 3. Install the App
Navigate to where you want the app (e.g., `/opt` or home dir):

```bash
cd /opt
git clone <YOUR_GITHUB_REPO_URL> network-monitor
cd network-monitor
```

### Backend Setup
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
# Copy example env
cp .env.example .env
# EDIT .env NOW with your keys/IPs
nano .env 
cd ..
```

### Frontend Setup
```bash
cd frontend
npm install
npm run build
cd ..
```

## 4. Setup Auto-Start (Systemd)

We will create two services: one for the Python API, one for serving the Frontend (using `serve` or similar).

**1. Backend Service** (`/etc/systemd/system/netmon-backend.service`)
```ini
[Unit]
Description=Network Monitor Backend
After=network.target

[Service]
User=root
WorkingDirectory=/opt/network-monitor/backend
Environment="PATH=/opt/network-monitor/backend/venv/bin:/usr/bin"
ExecStart=/opt/network-monitor/backend/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

**2. Frontend Service** (`/etc/systemd/system/netmon-frontend.service`)
*Note: For production, Nginx is better, but this is simple.*
```bash
npm install -g serve
```

File: `/etc/systemd/system/netmon-frontend.service`
```ini
[Unit]
Description=Network Monitor Frontend
After=network.target

[Service]
User=root
WorkingDirectory=/opt/network-monitor/frontend
ExecStart=/usr/bin/npx serve -s dist -l 3000
Restart=always

[Install]
WantedBy=multi-user.target
```

**Enable and Start:**
```bash
systemctl daemon-reload
systemctl enable --now netmon-backend
systemctl enable --now netmon-frontend
```

## 5. Updating the App
I have included an `update.sh` script in the root of the repo.
Whenever you push changes to GitHub, just SSH into your LXC and run:

```bash
cd /opt/network-monitor
./update.sh
```

This will pull the code, update dependencies, rebuild the frontend, and restart the services automatically.
