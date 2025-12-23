import axios from 'axios';

const API_URL = 'http://localhost:8000';

export const api = axios.create({
    baseURL: API_URL,
});

export const checkHealth = async () => {
    try {
        const res = await api.get('/health');
        return res.data;
    } catch (error) {
        console.error("Health check failed:", error);
        return { status: 'error' };
    }
};

export const triggerScan = async () => {
    const res = await api.post('/api/scan');
    return res.data;
};

export const getGraphData = async () => {
    const res = await api.get('/api/graph');
    return res.data;
};

export const getAlerts = async () => {
    const res = await api.get('/api/alerts');
    return res.data;
};
