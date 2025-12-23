#!/bin/bash

# Network Monitor Update Script
# Usage: ./update.sh

set -e  # Exit on error

echo "🔹 Starting App Update..."

# 1. Update Codebase
echo "📥 Pulling latest changes from Git..."
git pull

# 2. Update Backend Dependencies
echo "🐍 Updating Backend..."
cd backend
source ../venv/bin/activate || source venv/bin/activate || echo "⚠️ Warning: Could not activate venv, assuming global python or user needs to activate manually."
pip install -r requirements.txt
cd ..

# 3. Update Frontend (Check if node_modules exists, install if not)
echo "⚛️ Updating Frontend..."
cd frontend
if [ ! -d "node_modules" ]; then
    echo "   Installing Node dependencies..."
    npm install
fi
# Optional: npm install (if package.json changed) - uncomment if aggressive updates needed
# npm install 

echo "   Building Frontend..."
npm run build
cd ..

# 4. Restart Services
echo "Hz Restarting System Services..."
# Assuming systemd services are named netmon-backend and netmon-frontend
# Use sudo if not root
if [ "$EUID" -ne 0 ]; then
    sudo systemctl restart netmon-backend
    sudo systemctl restart netmon-frontend
else
    systemctl restart netmon-backend
    systemctl restart netmon-frontend
fi

echo "✅ Update Complete!"
