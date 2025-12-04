// src/index.js
// Ensure AFRAME is registered early so any aframe-extras or 3D plugins that expect window.AFRAME work.
// This import must come before other libraries that might pull in aframe-extras.
import 'aframe';

import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./App.css";

// Strict root mounting (React 18)
const container = document.getElementById("root");
const root = createRoot(container);
root.render(<App />);
