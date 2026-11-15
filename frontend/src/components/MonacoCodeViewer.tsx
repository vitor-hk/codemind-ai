import { useEffect, useRef } from "react";
import Editor, { type OnMount } from "@monaco-editor/react";
import { FileCode, ChevronRight, Crosshair } from "lucide-react";
import type { CodeSymbol, FileContent } from "../types/codemind";

interface MonacoCodeViewerProps {
  file: FileContent | null;
  highlightRange: [number, number] | null;
  fileSymbols: CodeSymbol[];
  onSelectSymbolRange: (range: [number, number]) => void;
  onAnalyzeImpact?: (symbolName: string) => void;
}

function mapMonacoLanguage(lang: string): string {
  const map: Record<string, string> = {
    Python: "python",
    TypeScript: "typescript",
    JavaScript: "javascript",
    Java: "java",
    JSON: "json",
    YAML: "yaml",
    Markdown: "markdown",
    HTML: "html",
    CSS: "css",
    SQL: "sql",
    Shell: "shell",
  };
  return map[lang] || "plaintext";
}

function symbolBadge(type: string) {
  const t = type.toLowerCase();
  if (t === "class") return { label: "CLS", cls: "text-amber-400 border-amber-500/30 bg-amber-500/10" };
  if (t === "interface") return { label: "IFC", cls: "text-sky-400 border-sky-500/30 bg-sky-500/10" };
  if (t === "method" || t === "constructor") return { label: "MTH", cls: "text-emerald-400 border-emerald-500/30 bg-emerald-500/10" };
  return { label: "FN", cls: "text-purple-300 border-purple-500/30 bg-purple-500/10" };
}

export function MonacoCodeViewer({
  file,
  highlightRange,
  fileSymbols,
  onSelectSymbolRange,
  onAnalyzeImpact,
}: MonacoCodeViewerProps) {
  const editorRef = useRef<any>(null);
  const monacoRef = useRef<any>(null);
  const decorationsRef = useRef<any>(null);

  const applyHighlight = () => {
    const editor = editorRef.current;
    const monaco = monacoRef.current;
    if (!editor || !monaco) return;
    if (decorationsRef.current) decorationsRef.current.clear();

    if (highlightRange) {
      const [startLine, endLine] = highlightRange;
      editor.revealLineInCenter(startLine);
      decorationsRef.current = editor.createDecorationsCollection([
        {
          range: new monaco.Range(startLine, 1, endLine, 1),
          options: { isWholeLine: true, className: "codemind-line-highlight" },
        },
      ]);
    } else {
      editor.setScrollTop(0);
    }
  };

  const handleEditorDidMount: OnMount = (editor, monaco) => {
    editorRef.current = editor;
    monacoRef.current = monaco;
    applyHighlight();
  };

  useEffect(() => {
    applyHighlight();
  }, [file?.relative_path, highlightRange]);

  if (!file) {
    return (
      <div className="h-full min-h-[520px] bg-[#0b0d12] border border-[#1c1f26] flex flex-col items-center justify-center text-zinc-500 text-xs font-mono gap-2">
        <FileCode className="w-6 h-6 text-zinc-700" />
        <span>NO_ACTIVE_BUFFER // Selecione um arquivo ou símbolo na árvore</span>
      </div>
    );
  }

  const pathParts = file.relative_path.split("/");

  return (
    <div className="h-full bg-[#0b0d12] border border-[#1c1f26] flex flex-col overflow-hidden">
      {/* Barra de Aba de Editor e Breadcrumb Técnico */}
      <div className="h-9 px-3 bg-[#08090c] border-b border-[#1c1f26] flex items-center justify-between text-xs font-mono">
        <div className="flex items-center gap-1.5 overflow-x-auto text-[11px]">
          <FileCode className="w-3.5 h-3.5 text-emerald-400 shrink-0 mr-1" />
          {pathParts.map((part, idx) => (
            <span key={idx} className="flex items-center gap-1 shrink-0">
              {idx > 0 && <ChevronRight className="w-3 h-3 text-zinc-600" />}
              <span className={idx === pathParts.length - 1 ? "text-zinc-100 font-semibold" : "text-zinc-500"}>
                {part}
              </span>
            </span>
          ))}
        </div>

        <div className="flex items-center gap-3 shrink-0 text-[11px]">
          {highlightRange && (
            <span className="px-2 py-0.5 bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
              SPAN L{highlightRange[0]}:{highlightRange[1]}
            </span>
          )}
          <span className="text-zinc-500 uppercase">{file.language}</span>
          <span className="text-zinc-600">|</span>
          <span className="text-zinc-400">{file.line_count} LOC</span>
        </div>
      </div>

      {/* Outline de Símbolos AST do Arquivo */}
      {fileSymbols.length > 0 && (
        <div className="px-3 py-1.5 bg-[#0d1017] border-b border-[#1c1f26] flex items-center gap-1.5 overflow-x-auto">
          <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-500 mr-1 shrink-0">
            AST_OUTLINE ({fileSymbols.length}):
          </span>
          {fileSymbols.map((sym) => {
            const b = symbolBadge(sym.symbol_type);
            return (
              <div
                key={sym.id}
                className="inline-flex items-center bg-[#12151e] border border-[#222634] hover:border-zinc-600 transition shrink-0"
              >
                <button
                  onClick={() => onSelectSymbolRange([sym.start_line, sym.end_line])}
                  className="px-2 py-0.5 text-[11px] font-mono flex items-center gap-1.5 text-zinc-300 hover:text-white cursor-pointer"
                  title={sym.signature}
                >
                  <span className={`text-[9px] px-1 border ${b.cls}`}>{b.label}</span>
                  <span>{sym.name}</span>
                  <span className="text-zinc-500 text-[10px]">:{sym.start_line}</span>
                </button>
                {onAnalyzeImpact && (
                  <button
                    onClick={() => onAnalyzeImpact(sym.qualified_name)}
                    className="px-1.5 py-0.5 border-l border-[#222634] text-zinc-500 hover:text-amber-400 hover:bg-amber-500/10 cursor-pointer"
                    title={`Calcular Blast Radius de ${sym.qualified_name}`}
                  >
                    <Crosshair className="w-3 h-3" />
                  </button>
                )}
              </div>
            );
          })}
        </div>
      )}

      <div className="flex-1 min-h-[470px] w-full">
        <Editor
          height="100%"
          theme="vs-dark"
          path={file.relative_path}
          language={mapMonacoLanguage(file.language)}
          value={file.content}
          onMount={handleEditorDidMount}
          options={{
            readOnly: true,
            minimap: { enabled: true, scale: 0.75 },
            fontSize: 12.5,
            fontFamily: "'JetBrains Mono', Menlo, Monaco, monospace",
            lineHeight: 20,
            scrollBeyondLastLine: false,
            wordWrap: "on",
            lineNumbers: "on",
            renderLineHighlight: "all",
            padding: { top: 10, bottom: 10 },
          }}
        />
      </div>
    </div>
  );
}
