// src/api.js
import axios from "axios";
const API_BASE = process.env.REACT_APP_API_URL || "http://127.0.0.1:8000/api";
export default axios.create({ baseURL: API_BASE, timeout: 45000 });
