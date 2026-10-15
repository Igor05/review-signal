import { useState } from "react";
import Projects from "./pages/Projects";
import Project from "./pages/Project";
import Report from "./pages/Report";

export default function App() {
  const [view, setView] = useState({ name: "projects" });

  return (
    <div className="min-h-screen">
      <nav className="no-print border-b border-rule bg-card">
        <div className="mx-auto flex max-w-5xl items-baseline gap-3 px-6 py-3">
          <button onClick={() => setView({ name: "projects" })} className="display text-base">
            Review Signal
          </button>
          <span className="font-mono text-[10px] uppercase tracking-widest text-graphite">
            what the reviews are costing you
          </span>
        </div>
      </nav>

      {view.name === "projects" && (
        <Projects onOpen={(id) => setView({ name: "project", id })} />
      )}
      {view.name === "project" && (
        <Project
          projectId={view.id}
          onBack={() => setView({ name: "projects" })}
          onReport={(id, runId) => setView({ name: "report", id, runId })}
        />
      )}
      {view.name === "report" && (
        <Report
          projectId={view.id}
          runId={view.runId}
          onBack={() => setView({ name: "project", id: view.id })}
        />
      )}
    </div>
  );
}
