import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./App.css";
import { initTheme } from "./theme";
import ErrorBoundary, { watchErrors } from "./ErrorBoundary";

initTheme();
watchErrors();

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(<React.StrictMode><ErrorBoundary><App /></ErrorBoundary></React.StrictMode>);
