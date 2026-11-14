from dataclasses import dataclass, field
import tree_sitter_java
import tree_sitter_javascript
import tree_sitter_python
import tree_sitter_typescript
from tree_sitter import Language, Node, Parser

from app.domain.enums import SymbolType

PYTHON_BUILTIN_CALLS: set[str] = {
    "print", "len", "range", "str", "int", "float", "bool", "list", "dict",
    "set", "tuple", "enumerate", "zip", "map", "filter", "isinstance", "getattr",
    "setattr", "hasattr", "super", "open", "min", "max", "sum", "sorted", "any", "all",
}

JS_TS_BUILTIN_CALLS: set[str] = {
    "console.log", "console.error", "console.warn", "setTimeout", "clearTimeout",
    "setInterval", "clearInterval", "parseInt", "parseFloat", "String", "Number",
    "Boolean", "Array", "Object", "Promise", "JSON.stringify", "JSON.parse", "fetch",
    "require",
}


@dataclass
class ExtractedSymbolDTO:
    name: str
    qualified_name: str
    symbol_type: SymbolType
    language: str
    file_path: str
    start_line: int
    end_line: int
    signature: str
    documentation: str | None = None
    parent_name: str | None = None
    calls: list[tuple[str, int]] = field(default_factory=list)
    bases: list[str] = field(default_factory=list)
    interfaces: list[str] = field(default_factory=list)


@dataclass
class FileAnalysisResultDTO:
    file_path: str
    language: str
    imports: list[tuple[str, int]] = field(default_factory=list)
    symbols: list[ExtractedSymbolDTO] = field(default_factory=list)


class TreeSitterAnalyzerEngine:
    """Motor unificado de análise sintática (AST) via Tree-sitter com Adapters por linguagem."""

    def __init__(self) -> None:
        self._languages: dict[str, Language] = {
            "Python": Language(tree_sitter_python.language()),
            "JavaScript": Language(tree_sitter_javascript.language()),
            "TypeScript": Language(tree_sitter_typescript.language_typescript()),
            "TSX": Language(tree_sitter_typescript.language_tsx()),
            "Java": Language(tree_sitter_java.language()),
        }

    def _get_parser(self, language: str, file_path: str) -> Parser | None:
        lang_key = language
        if language == "TypeScript" and file_path.endswith(".tsx"):
            lang_key = "TSX"
        ts_lang = self._languages.get(lang_key)
        if not ts_lang:
            return None
        return Parser(ts_lang)

    @staticmethod
    def _node_text(node: Node | None, source_bytes: bytes) -> str:
        if node is None:
            return ""
        return source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace").strip()

    @staticmethod
    def _first_line_signature(node: Node, source_bytes: bytes) -> str:
        raw = source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace")
        first_line = raw.splitlines()[0].strip() if raw else ""
        return first_line.rstrip("{:").strip()

    def analyze_file(self, file_path: str, language: str, content: str) -> FileAnalysisResultDTO:
        result = FileAnalysisResultDTO(file_path=file_path, language=language)
        parser = self._get_parser(language, file_path)
        if not parser:
            return result

        source_bytes = content.encode("utf-8", errors="replace")
        tree = parser.parse(source_bytes)
        root = tree.root_node

        if language == "Python":
            self._analyze_python(root, source_bytes, result)
        elif language in ("TypeScript", "JavaScript"):
            self._analyze_js_ts(root, source_bytes, result)
        elif language == "Java":
            self._analyze_java(root, source_bytes, result)

        return result

    def _analyze_python(
        self, root: Node, source_bytes: bytes, result: FileAnalysisResultDTO
    ) -> None:
        for child in root.children:
            actual = child
            if child.type == "decorated_definition":
                for sub in child.children:
                    if sub.type in ("function_definition", "class_definition"):
                        actual = sub
                        break

            if actual.type == "import_statement":
                line = actual.start_point[0] + 1
                for name_node in actual.children_by_field_name("name"):
                    imp_name = self._node_text(name_node, source_bytes).split(" as ")[0].strip()
                    if imp_name:
                        result.imports.append((imp_name, line))

            elif actual.type == "import_from_statement":
                line = actual.start_point[0] + 1
                mod_node = actual.child_by_field_name("module_name")
                mod_name = self._node_text(mod_node, source_bytes)
                for name_node in actual.children_by_field_name("name"):
                    sym = self._node_text(name_node, source_bytes).split(" as ")[0].strip()
                    full_imp = f"{mod_name}.{sym}" if mod_name else sym
                    if full_imp:
                        result.imports.append((full_imp, line))

            elif actual.type == "function_definition":
                sym = self._extract_python_function(
                    actual, source_bytes, result.file_path, parent_class=None
                )
                if sym:
                    result.symbols.append(sym)

            elif actual.type == "class_definition":
                cls_sym, methods = self._extract_python_class(
                    actual, source_bytes, result.file_path
                )
                if cls_sym:
                    result.symbols.append(cls_sym)
                    result.symbols.extend(methods)

    def _extract_python_function(
        self,
        node: Node,
        source_bytes: bytes,
        file_path: str,
        parent_class: str | None,
    ) -> ExtractedSymbolDTO | None:
        name_node = node.child_by_field_name("name")
        if not name_node:
            return None
        name = self._node_text(name_node, source_bytes)
        params_node = node.child_by_field_name("parameters")
        return_node = node.child_by_field_name("return_type")
        params_txt = self._node_text(params_node, source_bytes) or "()"
        ret_txt = f" -> {self._node_text(return_node, source_bytes)}" if return_node else ""
        signature = f"def {name}{params_txt}{ret_txt}"

        body_node = node.child_by_field_name("body")
        doc = self._extract_python_docstring(body_node, source_bytes)
        calls = self._extract_python_calls(body_node, source_bytes)

        if parent_class:
            sym_type = SymbolType.CONSTRUCTOR if name == "__init__" else SymbolType.METHOD
            qualified = f"{parent_class}.{name}"
        else:
            sym_type = SymbolType.FUNCTION
            qualified = name

        return ExtractedSymbolDTO(
            name=name,
            qualified_name=qualified,
            symbol_type=sym_type,
            language="Python",
            file_path=file_path,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            signature=signature,
            documentation=doc,
            parent_name=parent_class,
            calls=calls,
        )

    def _extract_python_class(
        self, node: Node, source_bytes: bytes, file_path: str
    ) -> tuple[ExtractedSymbolDTO | None, list[ExtractedSymbolDTO]]:
        name_node = node.child_by_field_name("name")
        if not name_node:
            return None, []
        cls_name = self._node_text(name_node, source_bytes)

        bases: list[str] = []
        superclasses_node = node.child_by_field_name("superclasses")
        if superclasses_node:
            for arg in superclasses_node.named_children:
                base_name = self._node_text(arg, source_bytes)
                if base_name and base_name != "object":
                    bases.append(base_name)

        body_node = node.child_by_field_name("body")
        doc = self._extract_python_docstring(body_node, source_bytes)

        methods: list[ExtractedSymbolDTO] = []
        class_calls: list[tuple[str, int]] = []
        if body_node:
            for item in body_node.children:
                actual = item
                if item.type == "decorated_definition":
                    for sub in item.children:
                        if sub.type == "function_definition":
                            actual = sub
                            break
                if actual.type == "function_definition":
                    m_sym = self._extract_python_function(
                        actual, source_bytes, file_path, parent_class=cls_name
                    )
                    if m_sym:
                        methods.append(m_sym)
                        class_calls.extend(m_sym.calls)

        base_str = f"({', '.join(bases)})" if bases else ""
        cls_dto = ExtractedSymbolDTO(
            name=cls_name,
            qualified_name=cls_name,
            symbol_type=SymbolType.CLASS,
            language="Python",
            file_path=file_path,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            signature=f"class {cls_name}{base_str}",
            documentation=doc,
            bases=bases,
            calls=class_calls,
        )
        return cls_dto, methods

    def _extract_python_docstring(self, body_node: Node | None, source_bytes: bytes) -> str | None:
        if not body_node or not body_node.named_children:
            return None
        first_stmt = body_node.named_children[0]
        if first_stmt.type == "expression_statement" and first_stmt.named_children:
            expr = first_stmt.named_children[0]
            if expr.type == "string":
                raw = self._node_text(expr, source_bytes)
                return raw.strip("\"' \n\t")
        return None

    def _extract_python_calls(
        self, scope_node: Node | None, source_bytes: bytes
    ) -> list[tuple[str, int]]:
        if not scope_node:
            return []
        calls: list[tuple[str, int]] = []
        seen: set[str] = set()

        stack = [scope_node]
        while stack:
            curr = stack.pop()
            if curr.type == "call":
                fn_node = curr.child_by_field_name("function")
                if fn_node:
                    raw_call = self._node_text(fn_node, source_bytes)
                    clean_call = raw_call.removeprefix("self.").removeprefix("cls.")
                    short_name = clean_call.split(".")[-1]
                    if (
                        short_name
                        and short_name not in PYTHON_BUILTIN_CALLS
                        and short_name not in seen
                    ):
                        seen.add(short_name)
                        calls.append((short_name, curr.start_point[0] + 1))
            stack.extend(reversed(curr.children))
        return calls

    def _analyze_js_ts(
        self, root: Node, source_bytes: bytes, result: FileAnalysisResultDTO
    ) -> None:
        stack = [root]
        while stack:
            node = stack.pop()

            if node.type == "import_statement":
                raw_imp = self._node_text(node, source_bytes)
                if "from" in raw_imp:
                    mod = raw_imp.split("from")[-1].strip(" ;'\"")
                    if mod:
                        result.imports.append((mod, node.start_point[0] + 1))
                continue

            if node.type == "interface_declaration":
                name_node = node.child_by_field_name("name")
                if name_node:
                    name = self._node_text(name_node, source_bytes)
                    result.symbols.append(
                        ExtractedSymbolDTO(
                            name=name,
                            qualified_name=name,
                            symbol_type=SymbolType.INTERFACE,
                            language=result.language,
                            file_path=result.file_path,
                            start_line=node.start_point[0] + 1,
                            end_line=node.end_point[0] + 1,
                            signature=f"interface {name}",
                        )
                    )
                continue

            if node.type == "class_declaration":
                name_node = node.child_by_field_name("name")
                if name_node:
                    cls_name = self._node_text(name_node, source_bytes)
                    bases: list[str] = []
                    for child in node.children:
                        if "heritage" in child.type or "extends" in child.type:
                            heritage_txt = self._node_text(child, source_bytes)
                            for token in heritage_txt.replace(",", " ").split():
                                if token not in ("extends", "implements"):
                                    bases.append(token)

                    cls_calls = self._extract_js_ts_calls(node, source_bytes)
                    result.symbols.append(
                        ExtractedSymbolDTO(
                            name=cls_name,
                            qualified_name=cls_name,
                            symbol_type=SymbolType.CLASS,
                            language=result.language,
                            file_path=result.file_path,
                            start_line=node.start_point[0] + 1,
                            end_line=node.end_point[0] + 1,
                            signature=self._first_line_signature(node, source_bytes),
                            bases=bases,
                            calls=cls_calls,
                        )
                    )

                    body_node = node.child_by_field_name("body")
                    if body_node:
                        for member in body_node.named_children:
                            if member.type == "method_definition":
                                m_name_node = member.child_by_field_name("name")
                                if m_name_node:
                                    m_name = self._node_text(m_name_node, source_bytes)
                                    m_type = (
                                        SymbolType.CONSTRUCTOR
                                        if m_name == "constructor"
                                        else SymbolType.METHOD
                                    )
                                    result.symbols.append(
                                        ExtractedSymbolDTO(
                                            name=m_name,
                                            qualified_name=f"{cls_name}.{m_name}",
                                            symbol_type=m_type,
                                            language=result.language,
                                            file_path=result.file_path,
                                            start_line=member.start_point[0] + 1,
                                            end_line=member.end_point[0] + 1,
                                            signature=self._first_line_signature(member, source_bytes),
                                            parent_name=cls_name,
                                            calls=self._extract_js_ts_calls(member, source_bytes),
                                        )
                                    )
                continue

            if node.type == "function_declaration":
                name_node = node.child_by_field_name("name")
                if name_node:
                    fn_name = self._node_text(name_node, source_bytes)
                    result.symbols.append(
                        ExtractedSymbolDTO(
                            name=fn_name,
                            qualified_name=fn_name,
                            symbol_type=SymbolType.FUNCTION,
                            language=result.language,
                            file_path=result.file_path,
                            start_line=node.start_point[0] + 1,
                            end_line=node.end_point[0] + 1,
                            signature=self._first_line_signature(node, source_bytes),
                            calls=self._extract_js_ts_calls(node, source_bytes),
                        )
                    )
                continue

            if node.type == "variable_declarator":
                name_node = node.child_by_field_name("name")
                val_node = node.child_by_field_name("value")
                if name_node and val_node and val_node.type in ("arrow_function", "function_expression"):
                    fn_name = self._node_text(name_node, source_bytes)
                    result.symbols.append(
                        ExtractedSymbolDTO(
                            name=fn_name,
                            qualified_name=fn_name,
                            symbol_type=SymbolType.FUNCTION,
                            language=result.language,
                            file_path=result.file_path,
                            start_line=node.start_point[0] + 1,
                            end_line=node.end_point[0] + 1,
                            signature=self._first_line_signature(node, source_bytes),
                            calls=self._extract_js_ts_calls(val_node, source_bytes),
                        )
                    )
                continue

            stack.extend(reversed(node.children))

    def _extract_js_ts_calls(
        self, scope_node: Node, source_bytes: bytes
    ) -> list[tuple[str, int]]:
        calls: list[tuple[str, int]] = []
        seen: set[str] = set()
        stack = [scope_node]
        while stack:
            curr = stack.pop()
            if curr.type == "call_expression":
                fn_node = curr.child_by_field_name("function")
                if fn_node:
                    raw = self._node_text(fn_node, source_bytes)
                    if raw not in JS_TS_BUILTIN_CALLS:
                        short = raw.removeprefix("this.").split(".")[-1]
                        if short and short not in JS_TS_BUILTIN_CALLS and short not in seen:
                            seen.add(short)
                            calls.append((short, curr.start_point[0] + 1))
            stack.extend(reversed(curr.children))
        return calls

    def _analyze_java(
        self, root: Node, source_bytes: bytes, result: FileAnalysisResultDTO
    ) -> None:
        stack = [root]
        while stack:
            node = stack.pop()
            if node.type == "import_declaration":
                raw = self._node_text(node, source_bytes).removeprefix("import").rstrip(";").strip()
                if raw:
                    result.imports.append((raw, node.start_point[0] + 1))
                continue

            if node.type in ("class_declaration", "interface_declaration"):
                name_node = node.child_by_field_name("name")
                if name_node:
                    cls_name = self._node_text(name_node, source_bytes)
                    sym_type = (
                        SymbolType.INTERFACE
                        if node.type == "interface_declaration"
                        else SymbolType.CLASS
                    )
                    bases: list[str] = []
                    super_node = node.child_by_field_name("superclass")
                    if super_node:
                        sup_txt = self._node_text(super_node, source_bytes).removeprefix("extends").strip()
                        if sup_txt:
                            bases.append(sup_txt)

                    result.symbols.append(
                        ExtractedSymbolDTO(
                            name=cls_name,
                            qualified_name=cls_name,
                            symbol_type=sym_type,
                            language="Java",
                            file_path=result.file_path,
                            start_line=node.start_point[0] + 1,
                            end_line=node.end_point[0] + 1,
                            signature=self._first_line_signature(node, source_bytes),
                            bases=bases,
                        )
                    )

                    body_node = node.child_by_field_name("body")
                    if body_node:
                        for member in body_node.named_children:
                            if member.type in ("method_declaration", "constructor_declaration"):
                                m_name_node = member.child_by_field_name("name")
                                if m_name_node:
                                    m_name = self._node_text(m_name_node, source_bytes)
                                    m_type = (
                                        SymbolType.CONSTRUCTOR
                                        if member.type == "constructor_declaration"
                                        else SymbolType.METHOD
                                    )
                                    result.symbols.append(
                                        ExtractedSymbolDTO(
                                            name=m_name,
                                            qualified_name=f"{cls_name}.{m_name}",
                                            symbol_type=m_type,
                                            language="Java",
                                            file_path=result.file_path,
                                            start_line=member.start_point[0] + 1,
                                            end_line=member.end_point[0] + 1,
                                            signature=self._first_line_signature(member, source_bytes),
                                            parent_name=cls_name,
                                            calls=self._extract_java_calls(member, source_bytes),
                                        )
                                    )
                continue

            stack.extend(reversed(node.children))

    def _extract_java_calls(
        self, scope_node: Node, source_bytes: bytes
    ) -> list[tuple[str, int]]:
        calls: list[tuple[str, int]] = []
        seen: set[str] = set()
        stack = [scope_node]
        while stack:
            curr = stack.pop()
            if curr.type == "method_invocation":
                name_node = curr.child_by_field_name("name")
                if name_node:
                    m_name = self._node_text(name_node, source_bytes)
                    if m_name and m_name not in ("println", "print", "format", "toString") and m_name not in seen:
                        seen.add(m_name)
                        calls.append((m_name, curr.start_point[0] + 1))
            stack.extend(reversed(curr.children))
        return calls
