import logging
import requests
import json
import os

logger = logging.getLogger(__name__)

class LocalAI:
    def __init__(self, base_url="http://localhost:11434", model="llama3"):
        self.base_url = os.getenv("OLLAMA_URL", base_url)
        self.model = os.getenv("OLLAMA_MODEL", model)
        self.enabled = False
        self._check_connection()

    def _check_connection(self):
        try:
            # Quick check to see if Ollama is running
            res = requests.get(f"{self.base_url}/api/tags", timeout=2)
            if res.status_code == 200:
                self.enabled = True
                logger.info(f"Connected to Local AI at {self.base_url} using model {self.model}")
            else:
                logger.warning(f"Local AI at {self.base_url} returned {res.status_code}")
        except Exception:
            logger.warning(f"Could not connect to Local AI at {self.base_url}. AI features will be limited.")

    def chat(self, user_prompt: str, context_data: dict):
        """
        Send a chat prompt to the local AI with network context.
        """
        if not self.enabled:
            return "Local AI is not connected. Please ensure Ollama is running."

        # Construct a system prompt with the current state
        system_prompt = (
            "You are a Network Operations center AI assistant. "
            "You are monitoring a home/lab network. "
            "Here is the current network state in JSON format:\n"
            f"{json.dumps(context_data, indent=2)}\n\n"
            "Answering guidelines:\n"
            "- Be concise and professional.\n"
            "- If the user asks about devices, look at the 'devices' list.\n"
            "- If the user asks about alerts, look at 'alerts'.\n"
            "- Highlight any security risks or anomalies.\n"
        )

        full_prompt = f"System Context: {system_prompt}\n\nUser: {user_prompt}\nAssistant:"

        try:
            # Using Ollama's generate API (simple stream=False for now)
            payload = {
                "model": self.model,
                "prompt": full_prompt,
                "stream": False
            }
            response = requests.post(f"{self.base_url}/api/generate", json=payload, timeout=30)
            if response.status_code == 200:
                return response.json().get("response", "No response from AI.")
            else:
                return f"Error from AI Provider: {response.text}"
        except Exception as e:
            logger.error(f"AI Chat Error: {e}")
            return "Failed to communicate with Local AI."

    def analyze(self, devices, opn_alerts):
        """
        Analyze network state for anomalies using the LLM.
        Returns a list of analytical alerts.
        """
        if not self.enabled:
            # Fallback to the old heuristic if AI is down
            return self._fallback_analyze(devices, opn_alerts)

        prompt = (
            "Analyze this network device list and OPNsense alerts for anomalies. "
            "Look for: Security risks, unknown devices, high load, or unusual services. "
            "Return ONLY a JSON array of objects with keys: 'severity' (info/warning/error), 'message' (string)."
            "Do not include markdown formatting or explanation text outside the JSON."
        )
        
        context = {
            "devices": devices[:50], # Limit context size
            "opn_alerts": opn_alerts
        }
        
        try:
            response = self.chat(prompt, context)
            # clean up response to ensure valid json
            response = response.strip()
            if response.startswith("```json"):
                response = response.split("```json")[1].split("```")[0]
            elif response.startswith("```"):
                 response = response.split("```")[1].split("```")[0]
            
            anomalies = json.loads(response)
            if isinstance(anomalies, list):
                # Add timestamps
                for a in anomalies:
                    a['timestamp'] = "Just now"
                return anomalies
        except Exception as e:
            logger.error(f"AI Analyze failed to parse: {e}")
            
        return self._fallback_analyze(devices, opn_alerts)

    def _fallback_analyze(self, devices, opn_alerts):
        """Original heuristic logic as fallback"""
        anomalies = []
        unknown_devices = [d for d in devices if d.get('hostname') in ["Unknown", ""]]
        if len(unknown_devices) > 0:
            anomalies.append({
                "severity": "info",
                "message": f"Basic Insight: Detected {len(unknown_devices)} devices with unknown hostnames.",
                "timestamp": "Now"
            })
        for alert in opn_alerts:
            if "CPU" in alert.get('message', ''):
                 anomalies.append({
                    "severity": "warning",
                    "message": "Basic Insight: High Firewall Load detected.",
                    "timestamp": "Now"
                })
        return anomalies
