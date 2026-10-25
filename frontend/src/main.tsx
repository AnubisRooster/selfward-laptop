import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./App.css";
import { initTheme } from "./theme";
import ErrorBoundary, { watchErrors } from "./ErrorBoundary";

initTheme();
watchErrors();

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(<React.StrictMode><ErrorBoundary><App /></ErrorBoundary></React.StrictMode>);

// The installed phone app (served over https by the private network) keeps its own files for a quick start. Not in the laptop window.
if ('serviceWorker' in navigator && location.protocol === 'https:') navigator.serviceWorker.register('/sw.js').catch(() => {});
