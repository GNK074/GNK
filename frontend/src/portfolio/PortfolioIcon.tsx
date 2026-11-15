import { ChartNoAxesCombined, Sparkles, TrendingUp } from "lucide-react";
import "./portfolio-icon.css";

export function PortfolioIcon({ size = 19 }: { size?: number }) {
  return (
    <span className="portfolio-icon" style={{ fontSize: size }} aria-hidden="true">
      <ChartNoAxesCombined className="portfolio-icon-chart" size="1em" />
      <TrendingUp className="portfolio-icon-growth" size="0.42em" />
      <Sparkles className="portfolio-icon-sparkle" size="0.47em" />
    </span>
  );
}
