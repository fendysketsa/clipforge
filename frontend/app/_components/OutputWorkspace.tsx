"use client";

import { Children, type ReactNode, useCallback, useEffect, useState } from "react";
import { Clock3, Layers3, Video } from "lucide-react";

type WorkspaceTab = "results" | "history";

type OutputWorkspaceProps = {
  children: ReactNode;
  resultCount: number;
  historyCount: number;
};

const tabFromHash = (): WorkspaceTab => window.location.hash === "#history" ? "history" : "results";

export function OutputWorkspace({ children, resultCount, historyCount }: OutputWorkspaceProps) {
  const panels = Children.toArray(children);
  const [activeTab, setActiveTab] = useState<WorkspaceTab>("results");

  const activateTab = useCallback((tab: WorkspaceTab, shouldScroll = false) => {
    setActiveTab(tab);
    window.history.replaceState(null, "", `#${tab}`);
    if (shouldScroll) {
      window.requestAnimationFrame(() => {
        document.getElementById("output-workspace")?.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    }
  }, []);

  useEffect(() => {
    const syncWithHash = () => activateTab(tabFromHash(), true);
    const openResults = () => activateTab("results", true);

    setActiveTab(tabFromHash());
    window.addEventListener("hashchange", syncWithHash);
    window.addEventListener("clipforge:open-results", openResults);
    return () => {
      window.removeEventListener("hashchange", syncWithHash);
      window.removeEventListener("clipforge:open-results", openResults);
    };
  }, [activateTab]);

  return (
    <section className="outputWorkspace" id="output-workspace" aria-label="Workspace hasil dan riwayat">
      <header className="outputWorkspaceHeader">
        <div className="outputWorkspaceTitle">
          <span>Library / workspace</span>
          <h2>Konten & Proses</h2>
          <p>Satu tempat untuk review output dan membuka pekerjaan sebelumnya.</p>
        </div>

        <div className="workspaceTabs" role="tablist" aria-label="Pilih tampilan workspace">
          <button
            aria-controls="workspace-results-panel"
            aria-selected={activeTab === "results"}
            className={activeTab === "results" ? "active" : ""}
            id="workspace-results-tab"
            role="tab"
            type="button"
            onClick={() => activateTab("results")}
          >
            <Video size={16} />
            <span><strong>Hasil Klip</strong><small>Output siap review</small></span>
            <b>{resultCount}</b>
          </button>
          <button
            aria-controls="workspace-history-panel"
            aria-selected={activeTab === "history"}
            className={activeTab === "history" ? "active" : ""}
            id="workspace-history-tab"
            role="tab"
            type="button"
            onClick={() => activateTab("history")}
          >
            <Clock3 size={16} />
            <span><strong>Riwayat</strong><small>Arsip proses</small></span>
            <b>{historyCount}</b>
          </button>
        </div>
      </header>

      <div
        aria-labelledby="workspace-results-tab"
        className={`outputWorkspacePane${activeTab === "results" ? " active" : ""}`}
        hidden={activeTab !== "results"}
        id="workspace-results-panel"
        role="tabpanel"
      >
        {panels[0]}
      </div>
      <div
        aria-labelledby="workspace-history-tab"
        className={`outputWorkspacePane${activeTab === "history" ? " active" : ""}`}
        hidden={activeTab !== "history"}
        id="workspace-history-panel"
        role="tabpanel"
      >
        {panels[1]}
      </div>

      <footer className="outputWorkspaceStatus">
        <Layers3 size={13} />
        <span>{activeTab === "results" ? `${resultCount} output tersedia` : `${historyCount} proses tersimpan`}</span>
        <i aria-hidden="true" />
        <span>Local index ready</span>
      </footer>
    </section>
  );
}
