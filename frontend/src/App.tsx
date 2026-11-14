import { useEffect, useState } from "react";
import axios from "axios";
import {
  Cpu,
  Database,
  HardDrive,
  RefreshCw,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  GitBranch,
  FolderGit2,
  FileCode2,
  Trash2,
  Plus,
  Loader2,
  Code2,
} from "lucide-react";

const API_BASE = "http://localhost:8000/api/v1";

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

interface Repository {
  id: string;
  name: string;
  description: string | null;
  source_type: string;
  source_url: string | null;
  default_branch: string;
  last_commit_hash: string | null;
  status: string;
  languages_stats: Record<string, number>;
  total_files: number;
  last_analyzed_at: string | null;
}

interface RepoFile {
  id: string;
  relative_path: string;
  language: string;
  extension: string;
  size_bytes: number;
  line_count: number;
  content_hash: string;
  is_ast_supported: boolean;
}

interface FileContent {
  repository_id: string;
  relative_path: string;
  language: string;
  line_count: number;
  content: string;
}

export function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [repos, setRepos] = useState<Repository[]>([]);
  const [selectedRepo, setSelectedRepo] = useState<Repository | null>(null);
  const [repoFiles, setRepoFiles] = useState<RepoFile[]>([]);
  const [selectedFile, setSelectedFile] = useState<FileContent | null>(null);

  const [gitUrl, setGitUrl] = useState("");
  const [customName, setCustomName] = useState("");
  const [importing, setImporting] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchAll = async () => {
    setLoading(true);
    setError(null);
    try {
      const [healthRes, reposRes] = await Promise.all([
        axios.get<HealthResponse>(`${API_BASE}/health`),
        axios.get<Repository[]>(`${API_BASE}/repositories`),
      ]);
      setHealth(healthRes.data);
      setRepos(reposRes.data);
      if (reposRes.data.length > 0 && !selectedRepo) {
        handleSelectRepo(reposRes.data[0]);
      }
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || "Erro ao conectar com a API.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAll();
  }, []);

  const handleSelectRepo = async (repo: Repository) => {
    setSelectedRepo(repo);
    setSelectedFile(null);
    try {
      const { data } = await axios.get<RepoFile[]>(`${API_BASE}/repositories/${repo.id}/files`);
      setRepoFiles(data);
      if (data.length > 0) {
        handleSelectFile(repo.id, data[0].relative_path);
      }
    } catch (err: any) {
      setError("Erro ao carregar arquivos do repositório.");
    }
  };

  const handleSelectFile = async (repoId: string, path: string) => {
    try {
      const { data } = await axios.get<FileContent>(
        `${API_BASE}/repositories/${repoId}/files/content`,
        { params: { path } }
      );
      setSelectedFile(data);
    } catch {
      setError("Não foi possível ler o arquivo selecionado.");
    }
  };

  const handleImportGit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!gitUrl.trim()) return;
    setImporting(true);
    setError(null);
    try {
      const { data } = await axios.post<Repository>(`${API_BASE}/repositories/git`, {
        git_url: gitUrl.trim(),
        name: customName.trim() || null,
      });
      setGitUrl("");
      setCustomName("");
      await fetchAll();
      await handleSelectRepo(data);
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Falha ao clonar o repositório Git.");
    } finally {
      setImporting(false);
    }
  };

  const handleDeleteRepo = async (repoId: string) => {
    try {
      await axios.delete(`${API_BASE}/repositories/${repoId}`);
      if (selectedRepo?.id === repoId) {
        setSelectedRepo(null);
        setRepoFiles([]);
        setSelectedFile(null);
      }
      await fetchAll();
    } catch {
      setError("Erro ao remover repositório.");
    }
  };

  const renderBadge = (status?: string) => {
    if (status === "healthy") {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
          <CheckCircle2 className="w-3.5 h-3.5" /> Healthy
        </span>
      );
    }
    if (status === "degraded") {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20">
          <AlertTriangle className="w-3.5 h-3.5" /> Degraded
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-rose-500/10 text-rose-400 border border-rose-500/20">
        <XCircle className="w-3.5 h-3.5" /> Unhealthy
      </span>
    );
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        <header className="flex items-center justify-between border-b border-zinc-800 pb-5">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold tracking-tight text-white">CodeMind AI</h1>
              <span className="text-xs font-mono px-2.5 py-0.5 rounded bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">
                Phase 2 · Repository Manager
              </span>
            </div>
            <p className="text-sm text-zinc-400 mt-1">
              Plataforma Inteligente de Análise Estática, Grafos de Dependência e Graph-RAG Local
            </p>
          </div>

          <button
            onClick={fetchAll}
            disabled={loading}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 text-sm font-medium transition cursor-pointer"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
            Atualizar
          </button>
        </header>

        {error && (
          <div className="p-4 rounded-xl bg-rose-950/40 border border-rose-800/60 text-rose-300 text-sm">
            {error}
          </div>
        )}

        {health && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="p-4 rounded-xl bg-zinc-900/60 border border-zinc-800/80 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Database className="w-5 h-5 text-indigo-400" />
                <div>
                  <div className="text-sm font-semibold">PostgreSQL + pgvector</div>
                  <div className="text-xs text-zinc-400 font-mono">
                    v{health.database.details.pgvector_version} · {repos.length} repos
                  </div>
                </div>
              </div>
              {renderBadge(health.database.status)}
            </div>

            <div className="p-4 rounded-xl bg-zinc-900/60 border border-zinc-800/80 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <HardDrive className="w-5 h-5 text-emerald-400" />
                <div>
                  <div className="text-sm font-semibold">Redis Cache & Jobs</div>
                  <div className="text-xs text-zinc-400 font-mono">Online</div>
                </div>
              </div>
              {renderBadge(health.redis.status)}
            </div>

            <div className="p-4 rounded-xl bg-zinc-900/60 border border-zinc-800/80 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Cpu className="w-5 h-5 text-amber-400" />
                <div>
                  <div className="text-sm font-semibold">Ollama Local Engine</div>
                  <div className="text-xs text-zinc-400 font-mono">
                    {health.ollama.details.configured_llm}
                  </div>
                </div>
              </div>
              {renderBadge(health.ollama.status)}
            </div>
          </div>
        )}

        {/* Importador de Repositório Git */}
        <form
          onSubmit={handleImportGit}
          className="p-5 rounded-xl bg-zinc-900/60 border border-zinc-800/80 flex flex-col md:flex-row gap-3 items-end"
        >
          <div className="flex-1 w-full">
            <label className="block text-xs font-medium text-zinc-400 mb-1.5">
              URL do Repositório Git (Público)
            </label>
            <input
              type="url"
              required
              placeholder="https://github.com/tiangolo/full-stack-fastapi-template"
              value={gitUrl}
              onChange={(e) => setGitUrl(e.target.value)}
              className="w-full px-3.5 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-sm text-zinc-100 focus:outline-none focus:border-indigo-500"
            />
          </div>
          <div className="w-full md:w-64">
            <label className="block text-xs font-medium text-zinc-400 mb-1.5">
              Nome de Exibição (Opcional)
            </label>
            <input
              type="text"
              placeholder="Ex: FastAPI Service"
              value={customName}
              onChange={(e) => setCustomName(e.target.value)}
              className="w-full px-3.5 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-sm text-zinc-100 focus:outline-none focus:border-indigo-500"
            />
          </div>
          <button
            type="submit"
            disabled={importing}
            className="w-full md:w-auto inline-flex items-center justify-center gap-2 px-5 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-sm font-medium text-white transition cursor-pointer"
          >
            {importing ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" /> Clonando & Analisando...
              </>
            ) : (
              <>
                <Plus className="w-4 h-4" /> Importar Repositório
              </>
            )}
          </button>
        </form>

        {/* Área do Repository Explorer */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Coluna 1: Repositórios */}
          <div className="lg:col-span-3 space-y-3">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-zinc-400 flex items-center gap-2">
              <FolderGit2 className="w-4 h-4 text-indigo-400" /> Repositórios ({repos.length})
            </h2>
            {repos.length === 0 ? (
              <div className="p-6 rounded-xl bg-zinc-900/40 border border-zinc-800/60 text-xs text-zinc-500 text-center">
                Nenhum repositório importado ainda. Cole uma URL do GitHub acima!
              </div>
            ) : (
              repos.map((r) => (
                <div
                  key={r.id}
                  onClick={() => handleSelectRepo(r)}
                  className={`p-4 rounded-xl border transition cursor-pointer space-y-2.5 ${
                    selectedRepo?.id === r.id
                      ? "bg-indigo-950/20 border-indigo-500/50"
                      : "bg-zinc-900/50 border-zinc-800/80 hover:border-zinc-700"
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <div className="font-semibold text-sm text-white">{r.name}</div>
                      <div className="text-xs text-zinc-400 flex items-center gap-1.5 mt-0.5 font-mono">
                        <GitBranch className="w-3 h-3" /> {r.default_branch} · {r.total_files} arq.
                      </div>
                    </div>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDeleteRepo(r.id);
                      }}
                      className="text-zinc-500 hover:text-rose-400 p-1"
                      title="Remover repositório"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>

                  <div className="flex flex-wrap gap-1.5">
                    {Object.entries(r.languages_stats).map(([lang, count]) => (
                      <span
                        key={lang}
                        className="text-[11px] font-mono px-2 py-0.5 rounded bg-zinc-800 text-zinc-300"
                      >
                        {lang}: {count}
                      </span>
                    ))}
                  </div>
                </div>
              ))
            )}
          </div>

          {/* Coluna 2: Árvore de Arquivos Filtrados */}
          <div className="lg:col-span-4 space-y-3">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-zinc-400 flex items-center gap-2">
              <FileCode2 className="w-4 h-4 text-emerald-400" /> Arquivos Indexados ({repoFiles.length})
            </h2>
            <div className="rounded-xl bg-zinc-900/50 border border-zinc-800/80 max-h-[540px] overflow-y-auto divide-y divide-zinc-800/50">
              {repoFiles.length === 0 ? (
                <div className="p-6 text-xs text-zinc-500 text-center">
                  Selecione um repositório para inspecionar seus arquivos.
                </div>
              ) : (
                repoFiles.map((f) => (
                  <div
                    key={f.id}
                    onClick={() => selectedRepo && handleSelectFile(selectedRepo.id, f.relative_path)}
                    className={`p-3 text-xs font-mono cursor-pointer transition flex items-center justify-between gap-2 ${
                      selectedFile?.relative_path === f.relative_path
                        ? "bg-indigo-500/15 text-indigo-300"
                        : "hover:bg-zinc-800/60 text-zinc-300"
                    }`}
                  >
                    <span className="truncate">{f.relative_path}</span>
                    <span className="shrink-0 text-[10px] px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400">
                      {f.language} · {f.line_count}L
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Coluna 3: Visualizador de Código */}
          <div className="lg:col-span-5 space-y-3">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-zinc-400 flex items-center gap-2">
              <Code2 className="w-4 h-4 text-amber-400" /> Inspecionar Código-Fonte
            </h2>
            <div className="rounded-xl bg-zinc-900/80 border border-zinc-800/80 overflow-hidden">
              {selectedFile ? (
                <>
                  <div className="px-4 py-2.5 bg-zinc-900 border-b border-zinc-800 flex items-center justify-between text-xs font-mono">
                    <span className="text-zinc-200">{selectedFile.relative_path}</span>
                    <span className="text-zinc-400">
                      {selectedFile.language} · {selectedFile.line_count} linhas
                    </span>
                  </div>
                  <pre className="p-4 text-xs font-mono text-zinc-300 overflow-x-auto max-h-[490px] overflow-y-auto leading-relaxed">
                    {selectedFile.content.split("\n").map((line, idx) => (
                      <div key={idx} className="table-row">
                        <span className="table-cell pr-4 text-right text-zinc-600 select-none">
                          {idx + 1}
                        </span>
                        <span className="table-cell whitespace-pre">{line}</span>
                      </div>
                    ))}
                  </pre>
                </>
              ) : (
                <div className="p-12 text-xs text-zinc-500 text-center">
                  Clique em qualquer arquivo para visualizar seu conteúdo numerado por linha.
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
