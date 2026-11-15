import { useEffect, useState } from "react";
import axios from "axios";
import {
  Terminal, FolderTree, GitFork, MessageSquareCode, Crosshair,
  FileText, Plus, RefreshCw, Search, Send, Loader2, GitBranch,
  ArrowUpRight, Command, Trash2, AlertCircle, X
} from "lucide-react";
import type {
  ArchitectureReport, ChatMessage, CodeSymbol, FileContent, GraphAnalysis,
  HealthResponse, ImpactAnalysis, NodeNeighborhood, RepoFile, Repository, SearchChunkHit
} from "./types/codemind";
import { MonacoCodeViewer } from "./components/MonacoCodeViewer";
import { ArchitectureGraph } from "./components/ArchitectureGraph";

const API_BASE = "http://localhost:8000/api/v1";
type NavSection = "workspace" | "topology" | "rag" | "blast" | "audit" | "overview";

export function App() {
  const [activeNav, setActiveNav] = useState<NavSection>("workspace");
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

  const [fileFilter, setFileFilter] = useState("");
  const [explorerMode, setExplorerMode] = useState<"files" | "symbols" | "hybrid">("files");
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

  const [showImportModal, setShowImportModal] = useState(false);
  const [showCmdPalette, setShowCmdPalette] = useState(false);
  const [cmdQuery, setCmdQuery] = useState("");
  const [gitUrl, setGitUrl] = useState("");
  const [customName, setCustomName] = useState("");
  const [importing, setImporting] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setShowCmdPalette((p) => !p);
      }
      if (e.key === "Escape") {
        setShowCmdPalette(false);
        setShowImportModal(false);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

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
      if (rRes.data.length > 0 && !selectedRepo) await handleSelectRepo(rRes.data[0]);
    } catch (err: any) {
      setError(err?.response?.data?.detail || "ERR_BACKEND_OFFLINE // Verifique porta 8000");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchOverview(); }, []);

  const handleSelectRepo = async (repo: Repository, scopeOverride?: "file" | "symbol") => {
    setSelectedRepo(repo);
    setError(null);
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
      if (filesRes.data.length > 0) await openFileInMonaco(repo.id, filesRes.data[0].relative_path, null, false);
    } catch {
      setError("ERR_REPO_LOAD // Falha ao carregar artefatos.");
    }
  };

  const openFileInMonaco = async (repoId: string, path: string, range: [number, number] | null = null, switchTab = false) => {
    try {
      const { data } = await axios.get<FileContent>(`${API_BASE}/repositories/${repoId}/files/content`, { params: { path } });
      setSelectedFile(data);
      setHighlightRange(range);
      if (switchTab) setActiveNav("workspace");
    } catch {
      setError(`ERR_FILE_READ // ${path}`);
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
      setShowImportModal(false);
      await fetchOverview();
      await handleSelectRepo(data);
      setActiveNav("workspace");
    } catch (err: any) {
      setError(err?.response?.data?.detail || "ERR_GIT_CLONE // Falha ao importar.");
    } finally {
      setImporting(false);
    }
  };

  const handleDeleteRepo = async (repoId: string) => {
    await axios.delete(`${API_BASE}/repositories/${repoId}`);
    if (selectedRepo?.id === repoId) {
      setSelectedRepo(null);
      setSelectedFile(null);
      setGraphData(null);
    }
    await fetchOverview();
  };

  const handleHybridSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedRepo || !searchQuery.trim()) return;
    setSearching(true);
    setExplorerMode("hybrid");
    try {
      const { data } = await axios.get(`${API_BASE}/repositories/${selectedRepo.id}/search`, {
        params: { q: searchQuery.trim(), limit: 12 },
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
    setChatHistory((prev) => [
      ...prev,
      {
        id: "temp-" + Date.now(),
        repository_id: selectedRepo.id,
        role: "user",
        intent: "QUERY",
        content: q,
        citations: [],
        execution_metrics: {},
        created_at: new Date().toISOString(),
      },
    ]);
    try {
      await axios.post(`${API_BASE}/repositories/${selectedRepo.id}/chat`, { question: q, max_tokens: 400 });
      const { data } = await axios.get<ChatMessage[]>(`${API_BASE}/repositories/${selectedRepo.id}/chat/history`);
      setChatHistory(data);
    } catch (err: any) {
      setError(err?.response?.data?.detail || "ERR_RAG_QUERY");
    } finally {
      setAskingChat(false);
    }
  };

  const runImpactAnalysis = async (targetName: string) => {
    if (!selectedRepo || !targetName.trim()) return;
    setImpactTarget(targetName);
    setLoadingImpact(true);
    setActiveNav("blast");
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
  const filteredFiles = repoFiles.filter((f) => f.relative_path.toLowerCase().includes(fileFilter.toLowerCase()));
  const filteredSymbols = symbols.filter((s) => s.qualified_name.toLowerCase().includes(fileFilter.toLowerCase()));

  const navItems: { id: NavSection; code: string; label: string; icon: any }[] = [
    { id: "workspace", code: "01", label: "Codebase & Hybrid RRF", icon: FolderTree },
    { id: "topology", code: "02", label: "Dependency Topology", icon: GitFork },
    { id: "rag", code: "03", label: "Graph-RAG Inspector", icon: MessageSquareCode },
    { id: "blast", code: "04", label: "Blast Radius Simulator", icon: Crosshair },
    { id: "audit", code: "05", label: "Architectural Audit", icon: FileText },
    { id: "overview", code: "06", label: "System Telemetry", icon: Terminal },
  ];

  return (
    <div className="h-screen w-screen bg-[#08090c] text-[#e4e4e7] flex flex-col overflow-hidden select-none">
      <header className="h-11 px-3 bg-[#0b0d12] border-b border-[#1c1f26] flex items-center justify-between gap-4 shrink-0">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 pr-3 border-r border-[#1c1f26]">
            <div className="w-2.5 h-2.5 bg-emerald-400 shadow-[0_0_8px_#10b981]" />
            <span className="font-mono text-xs font-bold tracking-wider text-white">
              CODEMIND<span className="text-emerald-400">//OS</span>
            </span>
          </div>
          <div className="flex items-center gap-2 font-mono text-xs">
            <span className="text-zinc-500">repo:</span>
            {selectedRepo ? (
              <select
                value={selectedRepo.id}
                onChange={(e) => {
                  const r = repos.find((x) => x.id === e.target.value);
                  if (r) handleSelectRepo(r);
                }}
                className="bg-[#12151e] border border-[#222634] px-2 py-1 text-xs font-mono text-emerald-300 cursor-pointer"
              >
                {repos.map((r) => (
                  <option key={r.id} value={r.id}>{r.name} ({r.total_files}f / {r.total_symbols}s)</option>
                ))}
              </select>
            ) : (
              <span className="text-zinc-500">none</span>
            )}
            {selectedRepo && (
              <span className="hidden md:inline-flex items-center gap-1 px-2 py-0.5 bg-[#12151e] border border-[#1c1f26] text-[11px] text-zinc-400">
                <GitBranch className="w-3 h-3 text-emerald-400" /> {selectedRepo.default_branch}
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowCmdPalette(true)}
            className="hidden sm:flex items-center gap-6 px-3 py-1 bg-[#12151e] border border-[#222634] text-xs font-mono text-zinc-400 cursor-pointer"
          >
            <span className="flex items-center gap-1.5"><Search className="w-3.5 h-3.5" /> Command Palette...</span>
            <kbd className="px-1.5 py-0.5 text-[10px] bg-[#08090c] border border-[#222634] text-zinc-300">⌘K</kbd>
          </button>
          <button
            onClick={() => setShowImportModal(true)}
            className="px-3 py-1 bg-emerald-500/15 border border-emerald-500/40 text-emerald-300 text-xs font-mono font-medium flex items-center gap-1.5 cursor-pointer"
          >
            <Plus className="w-3.5 h-3.5" /> CLONE_REPO
          </button>
          <button onClick={fetchOverview} className="p-1.5 bg-[#12151e] border border-[#222634] text-zinc-400 cursor-pointer">
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin text-emerald-400" : ""}`} />
          </button>
        </div>
      </header>

      <div className="flex-1 flex overflow-hidden">
        <aside className="w-56 bg-[#0b0d12] border-r border-[#1c1f26] flex flex-col justify-between shrink-0">
          <div className="p-2 space-y-1">
            <div className="px-2 py-1.5 text-[10px] font-mono uppercase tracking-widest text-zinc-500">MODULES</div>
            {navItems.map((item) => {
              const Icon = item.icon;
              const active = activeNav === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => setActiveNav(item.id)}
                  className={`w-full flex items-center justify-between px-2.5 py-2 text-xs font-mono cursor-pointer border-l-2 ${
                    active ? "border-emerald-400 bg-emerald-500/10 text-white font-semibold" : "border-transparent text-zinc-400 hover:bg-[#12151e]"
                  }`}
                >
                  <span className="flex items-center gap-2.5 truncate">
                    <Icon className={`w-3.5 h-3.5 ${active ? "text-emerald-400" : "text-zinc-500"}`} />
                    <span className="truncate">{item.label}</span>
                  </span>
                  <span className="text-[10px] text-zinc-600">{item.code}</span>
                </button>
              );
            })}
          </div>

          {selectedRepo && (
            <div className="p-3 m-2 bg-[#08090c] border border-[#1c1f26] space-y-1.5 font-mono text-[11px]">
              <div className="flex justify-between text-zinc-400"><span>FILES</span><span className="text-white">{selectedRepo.total_files}</span></div>
              <div className="flex justify-between text-zinc-400"><span>AST_NODES</span><span className="text-emerald-400">{selectedRepo.total_symbols}</span></div>
              <div className="flex justify-between text-zinc-400"><span>EDGES</span><span className="text-amber-400">{selectedRepo.total_dependencies}</span></div>
              <div className="flex justify-between text-zinc-400"><span>VECTORS</span><span className="text-sky-400">{selectedRepo.total_chunks ?? 0}</span></div>
            </div>
          )}
        </aside>

        <main className="flex-1 bg-[#08090c] bg-tech-grid overflow-y-auto p-4">
          {error && (
            <div className="mb-3 px-3 py-2 bg-rose-950/50 border border-rose-700/60 text-rose-300 text-xs font-mono flex items-center justify-between">
              <span className="flex items-center gap-2"><AlertCircle className="w-4 h-4" /> {error}</span>
              <button onClick={() => setError(null)}><X className="w-3.5 h-3.5" /></button>
            </div>
          )}

          {activeNav === "workspace" && (
            <div className="h-[calc(100vh-6.2rem)] grid grid-cols-12 gap-3">
              <div className="col-span-12 lg:col-span-4 bg-[#0b0d12] border border-[#1c1f26] flex flex-col overflow-hidden">
                <form onSubmit={handleHybridSearch} className="p-2 border-b border-[#1c1f26] flex gap-1.5">
                  <input
                    type="text"
                    placeholder="Hybrid RRF Search (pgvector + FTS)..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="flex-1 bg-[#08090c] border border-[#222634] px-2.5 py-1.5 text-xs font-mono text-white"
                  />
                  <button type="submit" disabled={searching} className="px-3 py-1.5 bg-emerald-500/15 border border-emerald-500/40 text-emerald-300 text-xs font-mono cursor-pointer">
                    {searching ? "..." : "RRF"}
                  </button>
                </form>

                <div className="grid grid-cols-3 border-b border-[#1c1f26] bg-[#08090c] font-mono text-[11px]">
                  <button onClick={() => setExplorerMode("files")} className={`py-1.5 border-b-2 cursor-pointer ${explorerMode === "files" ? "border-emerald-400 text-emerald-300" : "border-transparent text-zinc-500"}`}>FILES ({repoFiles.length})</button>
                  <button onClick={() => setExplorerMode("symbols")} className={`py-1.5 border-b-2 cursor-pointer ${explorerMode === "symbols" ? "border-emerald-400 text-emerald-300" : "border-transparent text-zinc-500"}`}>AST ({symbols.length})</button>
                  <button onClick={() => setExplorerMode("hybrid")} className={`py-1.5 border-b-2 cursor-pointer ${explorerMode === "hybrid" ? "border-emerald-400 text-emerald-300" : "border-transparent text-zinc-500"}`}>HITS ({searchHits.length})</button>
                </div>

                {explorerMode !== "hybrid" && (
                  <div className="p-2 border-b border-[#1c1f26]">
                    <input
                      type="text"
                      placeholder="Filter path or symbol..."
                      value={fileFilter}
                      onChange={(e) => setFileFilter(e.target.value)}
                      className="w-full bg-[#08090c] border border-[#1c1f26] px-2.5 py-1 text-[11px] font-mono text-zinc-300"
                    />
                  </div>
                )}

                <div className="flex-1 overflow-y-auto divide-y divide-[#141720] font-mono text-xs">
                  {explorerMode === "files" &&
                    filteredFiles.map((f) => (
                      <div
                        key={f.id}
                        onClick={() => selectedRepo && openFileInMonaco(selectedRepo.id, f.relative_path, null)}
                        className={`px-3 py-2 cursor-pointer flex justify-between ${selectedFile?.relative_path === f.relative_path ? "bg-emerald-500/10 text-emerald-300 border-l-2 border-emerald-400" : "hover:bg-[#12151e] text-zinc-300"}`}
                      >
                        <span className="truncate text-[11px]">{f.relative_path}</span>
                        <span className="text-[10px] text-zinc-500">{f.line_count}L</span>
                      </div>
                    ))}
                  {explorerMode === "symbols" &&
                    filteredSymbols.map((s) => (
                      <div key={s.id} onClick={() => selectedRepo && openFileInMonaco(selectedRepo.id, s.file_path, [s.start_line, s.end_line])} className="px-3 py-2 cursor-pointer hover:bg-[#12151e]">
                        <div className="flex justify-between"><span className="text-[11px] text-emerald-300 font-semibold truncate">{s.qualified_name}</span><span className="text-[9px] uppercase text-zinc-500">{s.symbol_type}</span></div>
                        <div className="text-[10px] text-zinc-500 truncate">{s.file_path}:L{s.start_line}-{s.end_line}</div>
                      </div>
                    ))}
                  {explorerMode === "hybrid" &&
                    searchHits.map((h, i) => (
                      <div key={h.chunk_id} onClick={() => selectedRepo && openFileInMonaco(selectedRepo.id, h.file_path, [h.start_line, h.end_line])} className="p-2.5 cursor-pointer hover:bg-[#12151e]">
                        <div className="flex justify-between"><span className="text-[11px] text-emerald-300 font-semibold">#{i + 1} {h.symbol_name}</span><span className="text-[10px] text-emerald-400">{h.rerank_score}</span></div>
                        <div className="text-[10px] text-zinc-500">{h.file_path}:L{h.start_line}-{h.end_line}</div>
                      </div>
                    ))}
                </div>
              </div>

              <div className="col-span-12 lg:col-span-8 h-full">
                <MonacoCodeViewer file={selectedFile} highlightRange={highlightRange} fileSymbols={currentFileSymbols} onSelectSymbolRange={setHighlightRange} onAnalyzeImpact={runImpactAnalysis} />
              </div>
            </div>
          )}

          {activeNav === "topology" && (
            <div className="grid grid-cols-12 gap-3">
              <div className="col-span-12 lg:col-span-8 space-y-2">
                <div className="p-2 bg-[#0b0d12] border border-[#1c1f26] flex justify-between font-mono text-xs">
                  <div className="flex gap-1.5">
                    <button onClick={() => { setGraphScope("file"); if (selectedRepo) handleSelectRepo(selectedRepo, "file"); }} className={`px-3 py-1 border cursor-pointer ${graphScope === "file" ? "bg-emerald-500/15 border-emerald-500/40 text-emerald-300" : "border-[#1c1f26] text-zinc-400"}`}>MODULE_GRAPH</button>
                    <button onClick={() => { setGraphScope("symbol"); if (selectedRepo) handleSelectRepo(selectedRepo, "symbol"); }} className={`px-3 py-1 border cursor-pointer ${graphScope === "symbol" ? "bg-emerald-500/15 border-emerald-500/40 text-emerald-300" : "border-[#1c1f26] text-zinc-400"}`}>SYMBOL_GRAPH</button>
                  </div>
                </div>
                <ArchitectureGraph graph={graphData} selectedNodeId={neighborhood?.node_id || null} onSelectNode={handleInspectGraphNode} />
              </div>
              <div className="col-span-12 lg:col-span-4 p-3 bg-[#0b0d12] border border-[#1c1f26] space-y-3 font-mono text-xs">
                <div className="text-emerald-400 font-bold">{neighborhood ? `NODE // ${neighborhood.node_id}` : "SELECT_A_GRAPH_NODE"}</div>
                {neighborhood && (
                  <>
                    <div><span className="text-zinc-400">DIRECT_CALLERS:</span> {neighborhood.direct_dependents.join(", ") || "None"}</div>
                    <div><span className="text-zinc-400">TRANSITIVE:</span> {neighborhood.transitive_dependents.slice(0, 8).join(", ") || "None"}</div>
                    <button onClick={() => runImpactAnalysis(neighborhood.node_id)} className="w-full py-1.5 bg-amber-500/20 border border-amber-500/40 text-amber-300 cursor-pointer">COMPUTE_BLAST_RADIUS</button>
                  </>
                )}
              </div>
            </div>
          )}

          {activeNav === "rag" && (
            <div className="h-[calc(100vh-6.2rem)] grid grid-cols-12 gap-3">
              <div className="col-span-12 lg:col-span-6 bg-[#0b0d12] border border-[#1c1f26] flex flex-col overflow-hidden">
                <div className="flex-1 p-3 overflow-y-auto space-y-3 font-mono text-xs">
                  {chatHistory.map((m) => (
                    <div key={m.id} className={`p-3 border space-y-2 ${m.role === "user" ? "bg-[#10141d] border-[#222838] ml-6" : "bg-[#08090c] border-[#1c1f26] mr-2"}`}>
                      <div className="text-[10px] text-emerald-400 font-bold">{m.role === "user" ? "ENGINEER_QUERY" : "CODEMIND_SYNTHESIS"}</div>
                      <div className="whitespace-pre-wrap font-sans text-xs text-zinc-200">{m.content}</div>
                      {m.citations?.length > 0 && (
                        <div className="flex flex-wrap gap-1.5 pt-2 border-t border-[#1c1f26]">
                          {m.citations.map((c, i) => (
                            <button key={i} onClick={() => selectedRepo && openFileInMonaco(selectedRepo.id, c.file_path, [c.start_line, c.end_line])} className="px-2 py-0.5 bg-emerald-500/10 border border-emerald-500/30 text-[10px] text-emerald-300 flex items-center gap-1 cursor-pointer">
                              {c.file_path}:L{c.start_line}-{c.end_line} <ArrowUpRight className="w-3 h-3" />
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                  {askingChat && (
                    <div className="p-3 bg-[#08090c] border border-emerald-500/40 flex items-center gap-2 text-emerald-300 text-xs font-mono">
                      <Loader2 className="w-4 h-4 animate-spin" /> SYNTHESIZING_GRAPH_RAG_RESPONSE...
                    </div>
                  )}
                </div>
                <form onSubmit={handleAskAssistant} className="p-2.5 bg-[#08090c] border-t border-[#1c1f26] flex gap-2">
                  <input type="text" required placeholder="Query codebase architecture or execution flow..." value={chatQuestion} onChange={(e) => setChatQuestion(e.target.value)} className="flex-1 bg-[#0b0d12] border border-[#222634] px-3 py-2 text-xs font-mono text-white" />
                  <button type="submit" disabled={askingChat} className="px-4 py-2 bg-emerald-500/20 border border-emerald-500/40 text-emerald-300 text-xs font-mono cursor-pointer"><Send className="w-3.5 h-3.5" /></button>
                </form>
              </div>
              <div className="col-span-12 lg:col-span-6 h-full">
                <MonacoCodeViewer file={selectedFile} highlightRange={highlightRange} fileSymbols={currentFileSymbols} onSelectSymbolRange={setHighlightRange} onAnalyzeImpact={runImpactAnalysis} />
              </div>
            </div>
          )}

          {activeNav === "blast" && (
            <div className="space-y-4 font-mono text-xs">
              <form onSubmit={(e) => { e.preventDefault(); runImpactAnalysis(impactTarget); }} className="p-3 bg-[#0b0d12] border border-[#1c1f26] flex gap-2">
                <input type="text" required placeholder="Symbol or file path (e.g. Session, Signer)..." value={impactTarget} onChange={(e) => setImpactTarget(e.target.value)} className="flex-1 bg-[#08090c] border border-[#222634] px-3 py-2 text-white" />
                <button type="submit" disabled={loadingImpact} className="px-5 py-2 bg-amber-500/20 border border-amber-500/40 text-amber-300 font-semibold cursor-pointer">COMPUTE_BLAST_RADIUS</button>
              </form>
              {impactResult && (
                <div className="p-4 bg-[#0b0d12] border border-[#1c1f26] space-y-2">
                  <div className="text-amber-300 font-bold">RISK: {impactResult.risk_level} ({impactResult.impact_score}/100) // {impactResult.resolved_file_path}</div>
                  {impactResult.technical_justifications.map((j, i) => <div key={i} className="text-zinc-300">:: {j}</div>)}
                </div>
              )}
            </div>
          )}

          {activeNav === "audit" && archReport && (
            <div className="p-4 bg-[#0b0d12] border border-[#1c1f26] space-y-3 font-mono text-xs">
              <div className="text-emerald-400 font-bold">ARCHITECTURAL_AUDIT // {archReport.repository_name}</div>
              <p className="text-zinc-300 font-sans">{archReport.overview}</p>
              {archReport.improvement_suggestions.map((s, i) => <div key={i} className="p-2 bg-[#08090c] border border-[#1c1f26] text-zinc-300">• {s}</div>)}
            </div>
          )}

          {activeNav === "overview" && (
            <div className="bg-[#0b0d12] border border-[#1c1f26] divide-y divide-[#141720] font-mono text-xs">
              {repos.map((r) => (
                <div key={r.id} onClick={() => { handleSelectRepo(r); setActiveNav("workspace"); }} className="p-3 hover:bg-[#12151e] cursor-pointer flex justify-between items-center">
                  <div><div className="text-white font-bold">{r.name}</div><div className="text-[10px] text-zinc-500">{r.source_url || "ARCHIVE"}</div></div>
                  <button onClick={(e) => { e.stopPropagation(); handleDeleteRepo(r.id); }} className="text-zinc-500 hover:text-rose-400"><Trash2 className="w-4 h-4" /></button>
                </div>
              ))}
            </div>
          )}
        </main>
      </div>

      <footer className="h-6 px-3 bg-[#0b0d12] border-t border-[#1c1f26] flex items-center justify-between text-[10px] font-mono text-zinc-400 shrink-0">
        <span>STATUS: {health?.overall_status?.toUpperCase() || "ONLINE"} | PGVECTOR {health?.database.details?.pgvector_version}</span>
        <span>LLM: {health?.ollama.details?.configured_llm || "qwen2.5-coder:7b"} | ⌘K PALETTE</span>
      </footer>

      {showImportModal && (
        <div className="fixed inset-0 z-50 bg-black/75 flex items-center justify-center p-4">
          <form onSubmit={handleImportGit} className="w-full max-w-md bg-[#0b0d12] border border-[#222634] p-4 space-y-3 font-mono text-xs">
            <div className="flex justify-between text-emerald-400 font-bold"><span>CLONE_GIT_REPOSITORY</span><button type="button" onClick={() => setShowImportModal(false)}><X className="w-4 h-4" /></button></div>
            <input type="url" required placeholder="https://github.com/pallets/itsdangerous" value={gitUrl} onChange={(e) => setGitUrl(e.target.value)} className="w-full bg-[#08090c] border border-[#222634] px-3 py-2 text-white" />
            <button type="submit" disabled={importing} className="w-full py-2 bg-emerald-500/20 border border-emerald-500/40 text-emerald-300 font-semibold cursor-pointer">{importing ? "INDEXING..." : "START_INGESTION"}</button>
          </form>
        </div>
      )}

      {showCmdPalette && (
        <div onClick={() => setShowCmdPalette(false)} className="fixed inset-0 z-50 bg-black/75 flex items-start justify-center pt-20 p-4">
          <div onClick={(e) => e.stopPropagation()} className="w-full max-w-lg bg-[#0b0d12] border border-[#262b38] font-mono text-xs">
            <div className="p-3 border-b border-[#1c1f26] flex items-center gap-2">
              <Command className="w-4 h-4 text-emerald-400" />
              <input autoFocus type="text" placeholder="Jump to module or file..." value={cmdQuery} onChange={(e) => setCmdQuery(e.target.value)} className="flex-1 bg-transparent text-white focus:outline-none" />
            </div>
            <div className="max-h-64 overflow-y-auto divide-y divide-[#141720]">
              {navItems.map((n) => (
                <div key={n.id} onClick={() => { setActiveNav(n.id); setShowCmdPalette(false); }} className="p-2.5 hover:bg-emerald-500/10 cursor-pointer flex justify-between">
                  <span className="text-emerald-300">MODULE // {n.label}</span><span className="text-zinc-500">{n.code}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
