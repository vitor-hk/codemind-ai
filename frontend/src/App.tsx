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
  Boxes,
  Network,
  Sparkles,
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
  total_symbols: number;
  total_dependencies: number;
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

interface CodeSymbol {
  id: string;
  name: string;
  qualified_name: string;
  symbol_type: string;
  language: string;
  file_path: string;
  parent_name: string | null;
  start_line: number;
  end_line: number;
  signature: string;
  documentation: string | null;
  dependencies: string[];
}

interface SymbolRelationship {
  id: string;
  source_symbol_name: string;
  source_file_path: string;
  target_name: string;
  target_file_path: string | null;
  relation_type: string;
  confidence: string;
  line_number: number;
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
  const [symbols, setSymbols] = useState<CodeSymbol[]>([]);
  const [relationships, setRelationships] = useState<SymbolRelationship[]>([]);
  const [selectedFile, setSelectedFile] = useState<FileContent | null>(null);
  const [highlightRange, setHighlightRange] = useState<[number, number] | null>(null);
  const [activeTab, setActiveTab] = useState<"files" | "symbols" | "relations">("symbols");

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
        await handleSelectRepo(reposRes.data[0]);
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
    setHighlightRange(null);
    try {
      const [filesRes, symRes, relRes] = await Promise.all([
        axios.get<RepoFile[]>(`${API_BASE}/repositories/${repo.id}/files`),
        axios.get<CodeSymbol[]>(`${API_BASE}/repositories/${repo.id}/symbols`),
        axios.get<SymbolRelationship[]>(`${API_BASE}/repositories/${repo.id}/relationships`),
      ]);
      setRepoFiles(filesRes.data);
      setSymbols(symRes.data);
      setRelationships(relRes.data);
      if (filesRes.data.length > 0) {
        await handleSelectFile(repo.id, filesRes.data[0].relative_path, null);
      }
    } catch {
      setError("Erro ao carregar dados de análise do repositório.");
    }
  };

  const handleSelectFile = async (
    repoId: string,
    path: string,
    range: [number, number] | null = null
  ) => {
    try {
      const { data } = await axios.get<FileContent>(
        `${API_BASE}/repositories/${repoId}/files/content`,
        { params: { path } }
      );
      setSelectedFile(data);
      setHighlightRange(range);
    } catch {
      setError("Não foi possível ler o arquivo selecionado.");
    }
  };

  const handleReanalyze = async (repo: Repository) => {
    try {
      setLoading(true);
      await axios.post(`${API_BASE}/repositories/${repo.id}/analyze`);
      const { data: updatedRepos } = await axios.get<Repository[]>(`${API_BASE}/repositories`);
      setRepos(updatedRepos);
      const refreshed = updatedRepos.find((r) => r.id === repo.id) || repo;
      await handleSelectRepo(refreshed);
    } catch {
      setError("Falha ao reexecutar análise sintática Tree-sitter.");
    } finally {
      setLoading(false);
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
        setSymbols([]);
        setRelationships([]);
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
              <span className="text-xs font-mono px-2.5 py-0.5 rounded bg-emerald-500/10 text-emerald-300 border border-emerald-500/20">
                Phase 3 · Tree-sitter AST Engine
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
              placeholder="https://github.com/navdeep-G/samplemod"
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
              placeholder="Ex: Sample Python Repo"
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
                <Loader2 className="w-4 h-4 animate-spin" /> Clonando & Extraindo AST...
              </>
            ) : (
              <>
                <Plus className="w-4 h-4" /> Importar Repositório
              </>
            )}
          </button>
        </form>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          <div className="lg:col-span-3 space-y-3">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-zinc-400 flex items-center gap-2">
              <FolderGit2 className="w-4 h-4 text-indigo-400" /> Repositórios ({repos.length})
            </h2>
            {repos.length === 0 ? (
              <div className="p-6 rounded-xl bg-zinc-900/40 border border-zinc-800/60 text-xs text-zinc-500 text-center">
                Nenhum repositório importado ainda.
              </div>
            ) : (
              repos.map((r) => (
                <div
                  key={r.id}
                  onClick={() => handleSelectRepo(r)}
                  className={`p-4 rounded-xl border transition cursor-pointer space-y-3 ${
                    selectedRepo?.id === r.id
                      ? "bg-indigo-950/20 border-indigo-500/50"
                      : "bg-zinc-900/50 border-zinc-800/80 hover:border-zinc-700"
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <div className="font-semibold text-sm text-white">{r.name}</div>
                      <div className="text-xs text-zinc-400 flex items-center gap-1.5 mt-0.5 font-mono">
                        <GitBranch className="w-3 h-3" /> {r.default_branch}
                      </div>
                    </div>
                    <div className="flex items-center gap-1">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleReanalyze(r);
                        }}
                        className="text-zinc-400 hover:text-indigo-400 p-1"
                        title="Reanalisar AST com Tree-sitter"
                      >
                        <Sparkles className="w-4 h-4" />
                      </button>
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
                  </div>

                  <div className="grid grid-cols-3 gap-1.5 text-center font-mono text-[11px]">
                    <div className="p-1.5 rounded bg-zinc-900 border border-zinc-800">
                      <div className="text-zinc-400">Arq</div>
                      <div className="text-white font-semibold">{r.total_files}</div>
                    </div>
                    <div className="p-1.5 rounded bg-zinc-900 border border-zinc-800">
                      <div className="text-zinc-400">Símbolos</div>
                      <div className="text-emerald-400 font-semibold">{r.total_symbols}</div>
                    </div>
                    <div className="p-1.5 rounded bg-zinc-900 border border-zinc-800">
                      <div className="text-zinc-400">Relações</div>
                      <div className="text-amber-400 font-semibold">{r.total_dependencies}</div>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>

          <div className="lg:col-span-4 space-y-3">
            <div className="flex items-center gap-1 bg-zinc-900 p-1 rounded-lg border border-zinc-800">
              <button
                onClick={() => setActiveTab("symbols")}
                className={`flex-1 py-1.5 px-2 rounded-md text-xs font-medium flex items-center justify-center gap-1.5 cursor-pointer ${
                  activeTab === "symbols"
                    ? "bg-indigo-600 text-white"
                    : "text-zinc-400 hover:text-zinc-200"
                }`}
              >
                <Boxes className="w-3.5 h-3.5" /> Símbolos ({symbols.length})
              </button>
              <button
                onClick={() => setActiveTab("relations")}
                className={`flex-1 py-1.5 px-2 rounded-md text-xs font-medium flex items-center justify-center gap-1.5 cursor-pointer ${
                  activeTab === "relations"
                    ? "bg-indigo-600 text-white"
                    : "text-zinc-400 hover:text-zinc-200"
                }`}
              >
                <Network className="w-3.5 h-3.5" /> Relações ({relationships.length})
              </button>
              <button
                onClick={() => setActiveTab("files")}
                className={`flex-1 py-1.5 px-2 rounded-md text-xs font-medium flex items-center justify-center gap-1.5 cursor-pointer ${
                  activeTab === "files"
                    ? "bg-indigo-600 text-white"
                    : "text-zinc-400 hover:text-zinc-200"
                }`}
              >
                <FileCode2 className="w-3.5 h-3.5" /> Arquivos ({repoFiles.length})
              </button>
            </div>

            <div className="rounded-xl bg-zinc-900/50 border border-zinc-800/80 max-h-[540px] overflow-y-auto divide-y divide-zinc-800/50">
              {activeTab === "symbols" &&
                (symbols.length === 0 ? (
                  <div className="p-6 text-xs text-zinc-500 text-center">
                    Nenhum símbolo extraído. Selecione um repositório ou clique no ícone de faísca para analisar.
                  </div>
                ) : (
                  symbols.map((s) => (
                    <div
                      key={s.id}
                      onClick={() =>
                        selectedRepo &&
                        handleSelectFile(selectedRepo.id, s.file_path, [s.start_line, s.end_line])
                      }
                      className="p-3 text-xs cursor-pointer hover:bg-zinc-800/60 transition space-y-1"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-mono font-semibold text-indigo-300 truncate">
                          {s.qualified_name}
                        </span>
                        <span className="shrink-0 text-[10px] font-mono uppercase px-1.5 py-0.5 rounded bg-zinc-800 text-emerald-400">
                          {s.symbol_type}
                        </span>
                      </div>
                      <div className="font-mono text-[11px] text-zinc-400 truncate">
                        {s.signature}
                      </div>
                      <div className="text-[10px] font-mono text-zinc-500">
                        {s.file_path}:{s.start_line}-{s.end_line}
                      </div>
                    </div>
                  ))
                ))}

              {activeTab === "relations" &&
                (relationships.length === 0 ? (
                  <div className="p-6 text-xs text-zinc-500 text-center">
                    Nenhuma relação estática identificada.
                  </div>
                ) : (
                  relationships.map((rel) => (
                    <div
                      key={rel.id}
                      onClick={() =>
                        selectedRepo &&
                        handleSelectFile(selectedRepo.id, rel.source_file_path, [
                          rel.line_number,
                          rel.line_number,
                        ])
                      }
                      className="p-3 text-xs cursor-pointer hover:bg-zinc-800/60 transition space-y-1 font-mono"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-amber-300 font-semibold">{rel.relation_type}</span>
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-300">
                          {rel.confidence}
                        </span>
                      </div>
                      <div className="text-zinc-200 truncate">
                        {rel.source_symbol_name} → {rel.target_name}
                      </div>
                      <div className="text-[10px] text-zinc-500">
                        {rel.source_file_path}:L{rel.line_number}
                      </div>
                    </div>
                  ))
                ))}

              {activeTab === "files" &&
                repoFiles.map((f) => (
                  <div
                    key={f.id}
                    onClick={() =>
                      selectedRepo && handleSelectFile(selectedRepo.id, f.relative_path, null)
                    }
                    className="p-3 text-xs font-mono cursor-pointer hover:bg-zinc-800/60 flex items-center justify-between gap-2"
                  >
                    <span className="truncate text-zinc-200">{f.relative_path}</span>
                    <span className="shrink-0 text-[10px] px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400">
                      {f.language} · {f.line_count}L
                    </span>
                  </div>
                ))}
            </div>
          </div>

          <div className="lg:col-span-5 space-y-3">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-zinc-400 flex items-center gap-2">
              <Code2 className="w-4 h-4 text-amber-400" /> Inspecionar Código-Fonte & Evidência AST
            </h2>
            <div className="rounded-xl bg-zinc-900/80 border border-zinc-800/80 overflow-hidden">
              {selectedFile ? (
                <>
                  <div className="px-4 py-2.5 bg-zinc-900 border-b border-zinc-800 flex items-center justify-between text-xs font-mono">
                    <span className="text-zinc-200">{selectedFile.relative_path}</span>
                    <span className="text-zinc-400">
                      {highlightRange
                        ? `Destacando L${highlightRange[0]}-L${highlightRange[1]}`
                        : `${selectedFile.language} · ${selectedFile.line_count} linhas`}
                    </span>
                  </div>
                  <pre className="p-4 text-xs font-mono text-zinc-300 overflow-x-auto max-h-[490px] overflow-y-auto leading-relaxed">
                    {selectedFile.content.split("\n").map((line, idx) => {
                      const lineNo = idx + 1;
                      const isHighlighted =
                        highlightRange &&
                        lineNo >= highlightRange[0] &&
                        lineNo <= highlightRange[1];
                      return (
                        <div
                          key={idx}
                          className={`table-row ${
                            isHighlighted ? "bg-indigo-500/20 text-white" : ""
                          }`}
                        >
                          <span className="table-cell pr-4 text-right text-zinc-500 select-none">
                            {lineNo}
                          </span>
                          <span className="table-cell whitespace-pre">{line}</span>
                        </div>
                      );
                    })}
                  </pre>
                </>
              ) : (
                <div className="p-12 text-xs text-zinc-500 text-center">
                  Clique em um símbolo AST, relação ou arquivo para abrir o código.
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
