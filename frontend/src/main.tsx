import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { App } from "./layouts/App";
import "./style.css";
import "./settings.css";
import "./compliance.css";
import "./brand-background.css";
import { initializeTheme } from "./services/theme";
initializeTheme();
createRoot(document.getElementById("root")!).render(
  <BrowserRouter>
    <App />
  </BrowserRouter>,
);
