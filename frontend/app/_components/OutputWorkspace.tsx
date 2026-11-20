import { Children, type ReactNode } from "react";

export function OutputWorkspace({ children, activeView }: { children: ReactNode; activeView: "results" | "history" }) {
  const panels = Children.toArray(children);
  return <section className="outputWorkspace" id="output-workspace" aria-label="Hasil dan riwayat produksi">
    <div className="outputWorkspacePane active" hidden={activeView !== "results"}>{activeView === "results" ? panels[0] : null}</div>
    <div className="outputWorkspacePane active" hidden={activeView !== "history"}>{activeView === "history" ? panels[1] : null}</div>
  </section>;
}
