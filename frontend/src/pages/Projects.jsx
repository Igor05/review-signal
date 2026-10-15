import { useEffect, useState } from "react";
import { api } from "../api";

export default function Projects({ onOpen }) {
  const [projects, setProjects] = useState([]);
  const [name, setName] = useState("");
  const [businessType, setBusinessType] = useState("");
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = () =>
    api
      .listProjects()
      .then(setProjects)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));

  useEffect(() => {
    load();
  }, []);

  const create = async () => {
    if (!name.trim()) return;
    try {
      const { id } = await api.createProject(name.trim(), businessType.trim());
      setName("");
      setBusinessType("");
      onOpen(id);
    } catch (err) {
      setError(err.message);
    }
  };

  const remove = async (id, projectName) => {
    if (!window.confirm(`Delete "${projectName}" and all its reviews?`)) return;
    await api.deleteProject(id);
    load();
  };

  return (
    <div className="mx-auto max-w-4xl px-6 py-14">
      <p className="eyebrow">Review audit workspace</p>
      <h1 className="display mt-2 text-5xl">Clients</h1>
      <p className="mt-3 max-w-lg text-graphite">
        One project per business you audit. Load their reviews, run the analysis, hand back the report.
      </p>

      <div className="mt-10 border border-rule bg-card p-6">
        <p className="eyebrow">New client</p>
        <div className="mt-4 grid gap-3 sm:grid-cols-[1fr_1fr_auto]">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && create()}
            placeholder="Business name"
            className="border border-rule bg-paper px-3 py-2 text-sm outline-none focus:border-forest"
          />
          <input
            value={businessType}
            onChange={(e) => setBusinessType(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && create()}
            placeholder="Type, e.g. dental clinic"
            className="border border-rule bg-paper px-3 py-2 text-sm outline-none focus:border-forest"
          />
          <button
            onClick={create}
            className="bg-forest px-5 py-2 font-mono text-xs uppercase tracking-widest text-paper hover:bg-ink"
          >
            Create
          </button>
        </div>
        <p className="mt-2 font-mono text-[11px] text-graphite">
          Business type sharpens the analysis. "independent pizzeria" beats "restaurant".
        </p>
      </div>

      {error && <p className="mt-6 font-mono text-sm text-signal-high">{error}</p>}

      <div className="mt-10">
        {loading && <p className="font-mono text-sm text-graphite">Loading…</p>}
        {!loading && projects.length === 0 && (
          <div className="border border-dashed border-rule px-6 py-14 text-center">
            <p className="display text-xl">No clients yet</p>
            <p className="mt-2 text-sm text-graphite">Create one above to start an audit.</p>
          </div>
        )}

        <ul className="divide-y divide-rule border-y border-rule">
          {projects.map((project) => (
            <li key={project.id} className="flex items-center gap-4 py-4">
              <button onClick={() => onOpen(project.id)} className="flex-1 text-left">
                <p className="display text-lg">{project.name}</p>
                <p className="font-mono text-[11px] text-graphite">
                  {project.review_count} reviews
                  {project.business_type && ` · ${project.business_type}`}
                  {project.latest_run_id ? " · report ready" : " · not analysed"}
                </p>
              </button>
              <button
                onClick={() => remove(project.id, project.name)}
                className="font-mono text-[11px] uppercase tracking-widest text-graphite hover:text-signal-high"
              >
                Delete
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
