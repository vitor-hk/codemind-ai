import { useEffect, useState } from "react";
import axios from "axios";
import {
  LayoutDashboard, FolderGit2, Share2, Bot, Code2, ShieldAlert,
  FileSpreadsheet, Plus, RefreshCw, Search, Send, Loader2, GitBranch, ArrowUpRight
} from "lucide-react";
import type {
  ArchitectureReport, ChatMessage, CodeSymbol, FileContent, GraphAnalysis,
  HealthResponse, ImpactAnalysis, NodeNeighborhood, RepoFile, Repository, SearchChunkHit
} from "./types/codemind";
import { MonacoCodeViewer } from "./components/MonacoCodeViewer";
import { ArchitectureGraph } from "./components/ArchitectureGraph";

const API_BASE = "http://localhost:8000/api/v1";
type NavSection = "dashboard" | "explorer" | "architecture" | "assistant" | "viewer" | "impact" | "reports";

export function App() {
  const [activeNav, setActiveNav] = useState<NavSection>("dashboard");
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [repos, setRepos] = useState<Repository[]>([]);
  const [selectedRepo, setSelectedRepo] = useState<Repository | null>(null);
  const [repoFiles, setRepoFiles] = useState<RepoFile[]>([]);
  const [symbols, setSymbols] = useState<CodeSymbol[]>([]);
  const [graphScope, setGraphScope] = useState<"file" | "symbol">("file");
  const [graphData, setGraphData] = useState<GraphAnalysis | null>(null);
  const [neighborhood, setNeighborhood] = useState<NodeNeighborhood | null>(null);
  const [selectedFile, setSelectedFile] = useState<FileContent | null>(null);
  const [highlightRange, setHighlightRange] = useState<[number, number] | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchHits, setSearchHits] = useState<SearchChunkHit[]>([]);
  const [searching, setSearching] = useState(false);
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [chatQuestion, setChatQuestion] = useState("");
  const [askingChat, setAskingChat] = useState(false);
  const [impactTarget, setImpactTarget] = useState("");
  const [impactResult, setImpactResult] = useState<ImpactAnalysis | null>(null);
  const [loadingImpact, setLoadingImpact] = useState(false);
  const [archReport, setArchReport] = useState<ArchitectureReport | null>(null);
  const [gitUrl, setGitUrl] = useState("");
  const [importing, setImporting] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchOverview = async () => {
    setLoading(true);
    setError(null);
    try {
      const [hRes, rRes] = await Promise.all([
        axios.get<HealthResponse>(`${API_BASE}/health`),
        axios.get<Repository[]>(`${API_BASE}/repositories`),
      ]);
      setHealth(hRes.data);
      setRepos(rRes.data);
      if (rRes.data.length > 0 && !selectedRepo) {
        await handleSelectRepo(rRes.data[0]);
      }
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Falha ao conectar ao backend na porta 8000.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchOverview(); }, []);

  const handleSelectRepo = async (repo: Repository, scopeOverride?: "file" | "symbol") => {
    setSelectedRepo(repo);
    const scope = scopeOverride || graphScope;
    try {
      const [filesRes, symRes, graphRes, chatRes, repRes] = await Promise.all([
        axios.get<RepoFile[]>(`${API_BASE}/repositories/${repo.id}/files`),
        axios.get<CodeSymbol[]>(`${API_BASE}/repositories/${repo.id}/symbols`),
        axios.get<GraphAnalysis>(`${API_BASE}/repositories/${repo.id}/graph`, { params: { scope, max_nodes: 80 } }),
        axios.get<ChatMessage[]>(`${API_BASE}/repositories/${repo.id}/chat/history`),
        axios.get<ArchitectureReport>(`${API_BASE}/repositories/${repo.id}/report`),
      ]);
      setRepoFiles(filesRes.data);
      setSymbols(symRes.data);
      setGraphData(graphRes.data);
      setChatHistory(chatRes.data);
      setArchReport(repRes.data);
      if (filesRes.data.length > 0) {
        await openFileInMonaco(repo.id, filesRes.data[0].relative_path, null, false);
      }
    } catch {
      setError("Erro ao carregar dados do repositório.");
    }
  };

  const openFileInMonaco = async (repoId: string, path: string, range: [number, number] | null = null, switchTab = false) => {
    try {
      const { data } = await axios.get<FileContent>(`${API_BASE}/repositories/${repoId}/files/content`, { params: { path } });
      setSelectedFile(data);
      setHighlightRange(range);
      if (switchTab) setActiveNav("viewer");
    } catch {
      setError(`Não foi possível abrir ${path}.`);
    }
  };

  const handleImportGit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!gitUrl.trim()) return;
    setImporting(true);
    try {
      const { data } = await axios.post<Repository>(`${API_BASE}/repositories/git`, { git_url: gitUrl.trim() });
      setGitUrl("");
      await fetchOverview();
      await handleSelectRepo(data);
      setActiveNav("explorer");
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Erro ao importar repositório.");
    } finally {
      setImporting(false);
    }
  };

  const handleHybridSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedRepo || !searchQuery.trim()) return;
    setSearching(true);
    try {
      const { data } = await axios.get(`${API_BASE}/repositories/${selectedRepo.id}/search`, {
        params: { q: searchQuery.trim(), limit: 10 },
      });
      setSearchHits(data.results);
      if (data.results.length > 0) {
        const top = data.results[0];
        await openFileInMonaco(selectedRepo.id, top.file_path, [top.start_line, top.end_line], false);
      }
    } finally {
      setSearching(false);
    }
  };

  const handleAskAssistant = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedRepo || !chatQuestion.trim()) return;
    setAskingChat(true);
    const q = chatQuestion.trim();
    setChatQuestion("");
    try {
      await axios.post(`${API_BASE}/repositories/${selectedRepo.id}/chat`, { question: q });
      const { data } = await axios.get<ChatMessage[]>(`${API_BASE}/repositories/${selectedRepo.id}/chat/history`);
      setChatHistory(data);
    } finally {
      setAskingChat(false);
    }
  };

  const runImpactAnalysis = async (targetName: string) => {
    if (!selectedRepo || !targetName.trim()) return;
    setImpactTarget(targetName);
    setLoadingImpact(true);
    setActiveNav("impact");
    try {
      const { data } = await axios.get<ImpactAnalysis>(`${API_BASE}/repositories/${selectedRepo.id}/impact`, {
        params: { target: targetName.trim() },
      });
      setImpactResult(data);
    } finally {
      setLoadingImpact(false);
    }
  };

  const handleInspectGraphNode = async (nodeId: string, filePath: string) => {
    if (!selectedRepo) return;
    const { data } = await axios.get<NodeNeighborhood>(`${API_BASE}/repositories/${selectedRepo.id}/graph/neighborhood`, {
      params: { node_id: nodeId, scope: graphScope },
    });
    setNeighborhood(data);
    await openFileInMonaco(selectedRepo.id, filePath, null, false);
  };

  const currentFileSymbols = symbols.filter((s) => s.file_path === selectedFile?.relative_path);
  const navItems: { id: NavSection; label: string; icon: any }[] = [
    { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
    { id: "explorer", label: "Repository Explorer", icon: FolderGit2 },
    { id: "architecture", label: "Architecture Graph", icon: Share2 },
    { id: "assistant", label: "AI Code Assistant", icon: Bot },
    { id: "viewer", label: "Monaco Code Viewer", icon: Code2 },
    { id: "impact", label: "Impact Analysis", icon: ShieldAlert },
    { id: "reports", label: "Architecture Reports", icon: FileSpreadsheet },
  ];

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex">
      <aside className="w-64 bg-zinc-900/80 border-r border-zinc-800 flex flex-col justify-between p-4 shrink-0">
        <div className="space-y-5">
          <div className="flex items-center gap-2.5 px-2">
            <div className="w-7 h-7 rounded-lg bg-indigo-600 flex items-center justify-center font-bold text-xs">CM</div>
            <div>
              <div className="text-sm font-bold text-white">CodeMind AI</div>
              <div className="text-[10px] font-mono text-zinc-400">Software Intelligence</div>
            </div>
          </div>

          {selectedRepo && (
            <select
              value={selectedRepo.id}
              onChange={(e) => {
                const r = repos.find((x) => x.id === e.target.value);
                if (r) handleSelectRepo(r);
              }}
              className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-2.5 py-2 text-xs font-semibold text-white"
            >
              {repos.map((r) => (
                <option key={r.id} value={r.id}>{r.name} ({r.total_files} arq)</option>
              ))}
            </select>
          )}

          <nav className="space-y-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              return (
                <button
                  key={item.id}
                  onClick={() => setActiveNav(item.id)}
                  className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-xs font-medium cursor-pointer ${
                    activeNav === item.id ? "bg-indigo-600 text-white" : "text-zinc-400 hover:bg-zinc-800/60"
                  }`}
                >
                  <Icon className="w-4 h-4" /> {item.label}
                </button>
              );
            })}
          </nav>
        </div>

        <div className="p-3 rounded-xl bg-zinc-950 border border-zinc-800 space-y-1.5 text-[11px] font-mono">
          <div>DB/pgvector: <span className="text-emerald-400">{health?.database.status || "..."}</span></div>
          <div>Redis: <span className="text-emerald-400">{health?.redis.status || "..."}</span></div>
          <div>Ollama: <span className="text-amber-400">{health?.ollama.status || "..."}</span></div>
        </div>
      </aside>

      <main className="flex-1 p-6 space-y-6 overflow-y-auto">
        <header className="flex flex-wrap items-center justify-between gap-4 border-b border-zinc-800 pb-4">
          <div>
            <h2 className="text-lg font-bold text-white">{navItems.find((n) => n.id === activeNav)?.label}</h2>
            <p className="text-xs text-zinc-400">Tree-sitter AST · NetworkX Graph · pgvector Hybrid Search · Ollama Graph-RAG</p>
          </div>
          <form onSubmit={handleImportGit} className="flex items-center gap-2">
            <input
              type="url"
              required
              placeholder="https://github.com/pallets/click"
              value={gitUrl}
              onChange={(e) => setGitUrl(e.target.value)}
              className="w-72 px-3 py-1.5 rounded-lg bg-zinc-900 border border-zinc-800 text-xs text-white"
            />
            <button type="submit" disabled={importing} className="px-3.5 py-1.5 rounded-lg bg-indigo-600 text-xs font-medium text-white flex items-center gap-1.5 cursor-pointer">
              {importing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />} Importar Git
            </button>
            <button type="button" onClick={fetchOverview} className="p-1.5 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-300 cursor-pointer">
              <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
            </button>
          </form>
        </header>

        {error && <div className="p-3 rounded-xl bg-rose-950/40 border border-rose-800 text-rose-300 text-xs">{error}</div>}

        {activeNav === "dashboard" && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 font-mono">
              <div className="p-5 rounded-xl bg-zinc-900/60 border border-zinc-800"><div className="text-xs text-zinc-400">Repositórios</div><div className="text-3xl font-bold mt-2">{repos.length}</div></div>
              <div className="p-5 rounded-xl bg-zinc-900/60 border border-zinc-800"><div className="text-xs text-zinc-400">Arquivos</div><div className="text-3xl font-bold text-indigo-400 mt-2">{repos.reduce((a, r) => a + r.total_files, 0)}</div></div>
              <div className="p-5 rounded-xl bg-zinc-900/60 border border-zinc-800"><div className="text-xs text-zinc-400">Símbolos AST</div><div className="text-3xl font-bold text-emerald-400 mt-2">{repos.reduce((a, r) => a + r.total_symbols, 0)}</div></div>
              <div className="p-5 rounded-xl bg-zinc-900/60 border border-zinc-800"><div className="text-xs text-zinc-400">Relações</div><div className="text-3xl font-bold text-amber-400 mt-2">{repos.reduce((a, r) => a + r.total_dependencies, 0)}</div></div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {repos.map((r) => (
                <div key={r.id} onClick={() => { handleSelectRepo(r); setActiveNav("explorer"); }} className="p-4 rounded-xl bg-zinc-900/50 border border-zinc-800 hover:border-indigo-500 cursor-pointer space-y-2">
                  <div className="font-bold text-sm text-white">{r.name}</div>
                  <div className="text-xs text-zinc-400 font-mono flex items-center gap-1.5"><GitBranch className="w-3.5 h-3.5" /> {r.default_branch} · {r.total_symbols} símbolos</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {activeNav === "explorer" && (
          <div className="space-y-4">
            <form onSubmit={handleHybridSearch} className="flex gap-2">
              <input type="text" placeholder="Busca Híbrida (pgvector + Full-Text Search + Reranking RRF)..." value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} className="flex-1 px-4 py-2 rounded-xl bg-zinc-900 border border-zinc-800 text-xs text-white" />
              <button type="submit" disabled={searching} className="px-5 py-2 rounded-xl bg-sky-600 text-xs font-medium text-white flex items-center gap-2 cursor-pointer">
                {searching ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />} Buscar
              </button>
            </form>
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
              <div className="lg:col-span-5 space-y-3">
                {searchHits.length > 0 && (
                  <div className="p-3 rounded-xl bg-zinc-900/70 border border-sky-500/30 space-y-2 max-h-56 overflow-y-auto">
                    {searchHits.map((h, i) => (
                      <div key={h.chunk_id} onClick={() => selectedRepo && openFileInMonaco(selectedRepo.id, h.file_path, [h.start_line, h.end_line])} className="p-2 rounded bg-zinc-950 border border-zinc-800 cursor-pointer font-mono text-xs">
                        <div className="text-sky-300 font-bold">#{i + 1} {h.symbol_name} (Score: {h.rerank_score})</div>
                        <div className="text-[10px] text-zinc-400">{h.file_path}:L{h.start_line}-{h.end_line}</div>
                      </div>
                    ))}
                  </div>
                )}
                <div className="rounded-xl bg-zinc-900/60 border border-zinc-800 max-h-[460px] overflow-y-auto divide-y divide-zinc-800/50">
                  {repoFiles.map((f) => (
                    <div key={f.id} onClick={() => selectedRepo && openFileInMonaco(selectedRepo.id, f.relative_path, null)} className="p-2.5 text-xs font-mono cursor-pointer hover:bg-zinc-800/50 flex justify-between">
                      <span className="truncate">{f.relative_path}</span>
                      <span className="text-[10px] text-zinc-400">{f.language}</span>
                    </div>
                  ))}
                </div>
              </div>
              <div className="lg:col-span-7">
                <MonacoCodeViewer file={selectedFile} highlightRange={highlightRange} fileSymbols={currentFileSymbols} onSelectSymbolRange={setHighlightRange} onAnalyzeImpact={runImpactAnalysis} />
              </div>
            </div>
          </div>
        )}

        {activeNav === "architecture" && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            <div className="lg:col-span-8 space-y-3">
              <div className="flex gap-2">
                <button onClick={() => { setGraphScope("file"); if (selectedRepo) handleSelectRepo(selectedRepo, "file"); }} className={`px-3 py-1.5 rounded-lg text-xs cursor-pointer ${graphScope === "file" ? "bg-indigo-600 text-white" : "bg-zinc-900 text-zinc-400"}`}>Grafo de Arquivos</button>
                <button onClick={() => { setGraphScope("symbol"); if (selectedRepo) handleSelectRepo(selectedRepo, "symbol"); }} className={`px-3 py-1.5 rounded-lg text-xs cursor-pointer ${graphScope === "symbol" ? "bg-indigo-600 text-white" : "bg-zinc-900 text-zinc-400"}`}>Grafo de Símbolos</button>
              </div>
              <ArchitectureGraph graph={graphData} selectedNodeId={neighborhood?.node_id || null} onSelectNode={handleInspectGraphNode} />
            </div>
            <div className="lg:col-span-4 p-4 rounded-xl bg-zinc-900/60 border border-zinc-800 space-y-3 font-mono text-xs">
              <div className="font-bold text-indigo-300">{neighborhood ? `Nó: ${neighborhood.node_id}` : "Clique em um nó do grafo"}</div>
              {neighborhood && (
                <>
                  <div><span className="text-emerald-400">Dependentes Diretos:</span> {neighborhood.direct_dependents.join(", ") || "Nenhum"}</div>
                  <div><span className="text-amber-400">Dependentes Transitivos:</span> {neighborhood.transitive_dependents.slice(0, 8).join(", ") || "Nenhum"}</div>
                  <button onClick={() => runImpactAnalysis(neighborhood.node_id)} className="w-full py-2 rounded-lg bg-amber-600 text-white font-semibold cursor-pointer">Analisar Impacto deste Componente</button>
                </>
              )}
            </div>
          </div>
        )}

        {activeNav === "assistant" && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            <div className="lg:col-span-6 flex flex-col h-[540px] rounded-xl bg-zinc-900/60 border border-zinc-800 overflow-hidden">
              <div className="flex-1 p-4 overflow-y-auto space-y-3">
                {chatHistory.map((m) => (
                  <div key={m.id} className={`p-3 rounded-xl text-xs space-y-2 ${m.role === "user" ? "bg-indigo-600/20 border border-indigo-500/30 ml-6" : "bg-zinc-950 border border-zinc-800 mr-4"}`}>
                    <div className="whitespace-pre-wrap">{m.content}</div>
                    {m.citations?.length > 0 && (
                      <div className="flex flex-wrap gap-1.5 pt-2 border-t border-zinc-800">
                        {m.citations.map((c, i) => (
                          <button key={i} onClick={() => selectedRepo && openFileInMonaco(selectedRepo.id, c.file_path, [c.start_line, c.end_line])} className="px-2 py-0.5 rounded bg-indigo-500/20 text-[10px] font-mono text-indigo-300 flex items-center gap-1 cursor-pointer">
                            {c.file_path}:L{c.start_line}-{c.end_line} <ArrowUpRight className="w-3 h-3" />
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
              <form onSubmit={handleAskAssistant} className="p-3 bg-zinc-900 border-t border-zinc-800 flex gap-2">
                <input type="text" required placeholder="Pergunte ao Graph-RAG sobre o código..." value={chatQuestion} onChange={(e) => setChatQuestion(e.target.value)} className="flex-1 px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-xs text-white" />
                <button type="submit" disabled={askingChat} className="px-4 py-2 rounded-lg bg-indigo-600 text-xs text-white flex items-center gap-1 cursor-pointer">
                  {askingChat ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />} Enviar
                </button>
              </form>
            </div>
            <div className="lg:col-span-6">
              <MonacoCodeViewer file={selectedFile} highlightRange={highlightRange} fileSymbols={currentFileSymbols} onSelectSymbolRange={setHighlightRange} onAnalyzeImpact={runImpactAnalysis} />
            </div>
          </div>
        )}

        {activeNav === "viewer" && (
          <MonacoCodeViewer file={selectedFile} highlightRange={highlightRange} fileSymbols={currentFileSymbols} onSelectSymbolRange={setHighlightRange} onAnalyzeImpact={runImpactAnalysis} />
        )}

        {activeNav === "impact" && (
          <div className="space-y-4">
            <form onSubmit={(e) => { e.preventDefault(); runImpactAnalysis(impactTarget); }} className="flex gap-2">
              <input type="text" required placeholder="Símbolo ou arquivo (ex: BaseCommand)..." value={impactTarget} onChange={(e) => setImpactTarget(e.target.value)} className="flex-1 px-4 py-2 rounded-xl bg-zinc-900 border border-zinc-800 text-xs text-white" />
              <button type="submit" disabled={loadingImpact} className="px-5 py-2 rounded-xl bg-amber-600 text-xs font-semibold text-white cursor-pointer">
                {loadingImpact ? "Calculando..." : "Simular Impacto"}
              </button>
            </form>
            {impactResult && (
              <div className="p-5 rounded-xl bg-zinc-900/60 border border-zinc-800 space-y-3 text-xs font-mono">
                <div className="text-base font-bold text-amber-300">Risco: {impactResult.risk_level} (Score: {impactResult.impact_score}/100) — {impactResult.resolved_file_path}</div>
                {impactResult.technical_justifications.map((j, i) => <div key={i} className="text-zinc-300">• {j}</div>)}
              </div>
            )}
          </div>
        )}

        {activeNav === "reports" && archReport && (
          <div className="p-5 rounded-xl bg-zinc-900/60 border border-zinc-800 space-y-4 text-xs">
            <div className="text-base font-bold text-white">{archReport.repository_name} — Relatório de Arquitetura</div>
            <p className="text-zinc-300">{archReport.overview}</p>
            <div className="space-y-2">
              {archReport.improvement_suggestions.map((s, i) => <div key={i} className="p-2.5 rounded bg-zinc-950 border border-zinc-800 text-emerald-300">• {s}</div>)}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
