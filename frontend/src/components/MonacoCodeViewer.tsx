import { useEffect, useRef } from "react";
import Editor, { type OnMount } from "@monaco-editor/react";
import { Code2, Boxes, Sparkles } from "lucide-react";
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
      <div className="h-[540px] rounded-xl bg-zinc-900/60 border border-zinc-800 flex flex-col items-center justify-center text-zinc-500 text-xs gap-2">
        <Code2 className="w-8 h-8 text-zinc-700" />
        <span>Selecione um arquivo, símbolo AST ou citação para abrir no Monaco Editor.</span>
      </div>
    );
  }

  return (
    <div className="rounded-xl bg-zinc-900/90 border border-zinc-800 overflow-hidden flex flex-col">
      <div className="px-4 py-2.5 bg-zinc-900 border-b border-zinc-800 flex items-center justify-between gap-2 text-xs font-mono">
        <span className="text-zinc-100 font-semibold truncate">{file.relative_path}</span>
        <span className="text-zinc-400">
          {highlightRange
            ? `Evidência L${highlightRange[0]}–L${highlightRange[1]}`
            : `${file.language} · ${file.line_count} linhas`}
        </span>
      </div>

      {fileSymbols.length > 0 && (
        <div className="px-3 py-2 bg-zinc-950/70 border-b border-zinc-800/80 flex items-center gap-1.5 overflow-x-auto">
          <span className="text-[10px] font-mono uppercase text-zinc-500 flex items-center gap-1 shrink-0">
            <Boxes className="w-3 h-3 text-emerald-400" /> Símbolos:
          </span>
          {fileSymbols.map((sym) => (
            <div key={sym.id} className="inline-flex items-center rounded bg-zinc-900 border border-zinc-800 shrink-0">
              <button
                onClick={() => onSelectSymbolRange([sym.start_line, sym.end_line])}
                className="px-2 py-0.5 text-[11px] font-mono text-zinc-300 hover:text-indigo-300 cursor-pointer"
              >
                {sym.name} <span className="text-zinc-500">L{sym.start_line}</span>
              </button>
              {onAnalyzeImpact && (
                <button
                  onClick={() => onAnalyzeImpact(sym.qualified_name)}
                  className="px-1.5 py-0.5 border-l border-zinc-800 text-amber-400 hover:bg-amber-500/10 cursor-pointer"
                  title="Simular impacto"
                >
                  <Sparkles className="w-3 h-3" />
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      <div className="h-[500px] w-full">
        <Editor
          height="100%"
          theme="vs-dark"
          path={file.relative_path}
          language={mapMonacoLanguage(file.language)}
          value={file.content}
          onMount={handleEditorDidMount}
          options={{
            readOnly: true,
            minimap: { enabled: true },
            fontSize: 12,
            scrollBeyondLastLine: false,
            wordWrap: "on",
            lineNumbers: "on",
          }}
        />
      </div>
    </div>
  );
}
