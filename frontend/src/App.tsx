import { useEffect, useState } from "react";
import axios from "axios";
import { Cpu, Database, HardDrive, RefreshCw, CheckCircle2, AlertTriangle, XCircle } from "lucide-react";

interface ComponentStatus {
  status: "healthy" | "degraded" | "unhealthy";
  details: Record<string, any>;
}

interface HealthResponse {
  app_name: string;
  version: string;
  overall_status: "healthy" | "degraded" | "unhealthy";
  database: ComponentStatus;
  redis: ComponentStatus;
  ollama: ComponentStatus;
}

export function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchHealth = async () => {
    setLoading(true);
    setError(null);
    try {
      const { data } = await axios.get<HealthResponse>("http://localhost:8000/api/v1/health");
      setHealth(data);
    } catch (err: any) {
      setError(err?.message || "Não foi possível conectar ao backend FastAPI (porta 8000).");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHealth();
  }, []);

  const renderBadge = (status?: string) => {
    if (status === "healthy") {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
          <CheckCircle2 className="w-3.5 h-3.5" /> Healthy
        </span>
      );
    }
    if (status === "degraded") {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20">
          <AlertTriangle className="w-3.5 h-3.5" /> Degraded
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-rose-500/10 text-rose-400 border border-rose-500/20">
        <XCircle className="w-3.5 h-3.5" /> Unhealthy
      </span>
    );
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 p-8">
      <div className="max-w-5xl mx-auto space-y-8">
        <header className="flex items-center justify-between border-b border-zinc-800 pb-6">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold tracking-tight text-white">CodeMind AI</h1>
              <span className="text-xs font-mono px-2 py-0.5 rounded bg-zinc-800 text-zinc-300">
                v{health?.version || "0.1.0"} · Phase 1 Foundation
              </span>
            </div>
            <p className="text-sm text-zinc-400 mt-1">
              Plataforma Inteligente de Análise Estática, Grafos de Dependência e Graph-RAG Local
            </p>
          </div>

          <button
            onClick={fetchHealth}
            disabled={loading}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 text-sm font-medium transition cursor-pointer"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
            Atualizar Diagnóstico
          </button>
        </header>

        {error && (
          <div className="p-4 rounded-xl bg-rose-950/40 border border-rose-800/60 text-rose-300 text-sm">
            {error}
          </div>
        )}

        {health && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            {/* Card PostgreSQL + pgvector */}
            <div className="p-5 rounded-xl bg-zinc-900/60 border border-zinc-800/80 space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <Database className="w-5 h-5 text-indigo-400" />
                  <h2 className="font-semibold text-sm">PostgreSQL + pgvector</h2>
                </div>
                {renderBadge(health.database.status)}
              </div>
              <div className="text-xs text-zinc-400 space-y-1.5 font-mono">
                <div>pgvector: {String(health.database.details.pgvector_version || "N/A")}</div>
                <div>Repositórios: {health.database.details.repositories_registered ?? 0}</div>
              </div>
            </div>

            {/* Card Redis */}
            <div className="p-5 rounded-xl bg-zinc-900/60 border border-zinc-800/80 space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <HardDrive className="w-5 h-5 text-emerald-400" />
                  <h2 className="font-semibold text-sm">Redis Cache & Jobs</h2>
                </div>
                {renderBadge(health.redis.status)}
              </div>
              <div className="text-xs text-zinc-400 space-y-1.5 font-mono">
                <div>Conectado: {String(health.redis.details.connected)}</div>
              </div>
            </div>

            {/* Card Ollama Local */}
            <div className="p-5 rounded-xl bg-zinc-900/60 border border-zinc-800/80 space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <Cpu className="w-5 h-5 text-amber-400" />
                  <h2 className="font-semibold text-sm">Ollama Inference Engine</h2>
                </div>
                {renderBadge(health.ollama.status)}
              </div>
              <div className="text-xs text-zinc-400 space-y-1.5 font-mono">
                <div>LLM: {health.ollama.details.configured_llm} ({health.ollama.details.llm_ready ? "OK" : "Faltando"})</div>
                <div>Embed: {health.ollama.details.configured_embedding} ({health.ollama.details.embedding_ready ? "OK" : "Faltando"})</div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;