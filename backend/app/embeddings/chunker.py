import hashlib
import uuid
from dataclasses import dataclass
from app.domain.enums import SymbolType
from app.infrastructure.database.models import CodeSymbolModel, RepositoryFileModel

MAX_LINES_PER_CHUNK = 90
FALLBACK_BLOCK_LINES = 60


@dataclass
class SmartCodeChunkDTO:
    file_id: uuid.UUID
    symbol_id: uuid.UUID | None
    file_path: str
    language: str
    class_name: str | None
    symbol_name: str
    element_type: str
    signature: str
    start_line: int
    end_line: int
    content_hash: str
    contextual_content: str
    raw_code: str


class ASTSmartChunker:
    """Estratégia de chunking semântico orientada à árvore sintática (AST)."""

    def chunk_file(
        self,
        file_model: RepositoryFileModel,
        file_content: str,
        symbols: list[CodeSymbolModel],
    ) -> list[SmartCodeChunkDTO]:
        lines = file_content.splitlines()
        if not lines:
            return []

        chunks: list[SmartCodeChunkDTO] = []

        if not symbols:
            return self._chunk_plain_file(file_model, lines)

        classes_with_methods = {
            s.parent_name for s in symbols if s.parent_name is not None
        }

        for sym in symbols:
            start_idx = max(0, sym.start_line - 1)
            end_idx = min(len(lines), sym.end_line)

            if (
                sym.symbol_type == SymbolType.CLASS
                and sym.name in classes_with_methods
                and (end_idx - start_idx) > 35
            ):
                end_idx = min(len(lines), start_idx + 25)

            span_lines = lines[start_idx:end_idx]
            if not span_lines:
                continue

            if len(span_lines) <= MAX_LINES_PER_CHUNK:
                chunks.append(
                    self._build_dto(
                        file_model=file_model,
                        symbol=sym,
                        start_line=start_idx + 1,
                        end_line=end_idx,
                        code_lines=span_lines,
                        part_index=None,
                    )
                )
            else:
                step = MAX_LINES_PER_CHUNK - 10
                part = 1
                for offset in range(0, len(span_lines), step):
                    sub_lines = span_lines[offset : offset + MAX_LINES_PER_CHUNK]
                    if not sub_lines:
                        break
                    sub_start = start_idx + 1 + offset
                    sub_end = sub_start + len(sub_lines) - 1
                    chunks.append(
                        self._build_dto(
                            file_model=file_model,
                            symbol=sym,
                            start_line=sub_start,
                            end_line=sub_end,
                            code_lines=sub_lines,
                            part_index=part,
                        )
                    )
                    part += 1

        return chunks

    def _chunk_plain_file(
        self, file_model: RepositoryFileModel, lines: list[str]
    ) -> list[SmartCodeChunkDTO]:
        chunks: list[SmartCodeChunkDTO] = []
        step = FALLBACK_BLOCK_LINES - 10
        part = 1
        for offset in range(0, len(lines), step):
            sub_lines = lines[offset : offset + FALLBACK_BLOCK_LINES]
            if not sub_lines:
                break
            start_line = offset + 1
            end_line = start_line + len(sub_lines) - 1
            raw_code = "\n".join(sub_lines)
            sym_name = f"{file_model.relative_path.split('/')[-1]}#block_{part}"
            header = (
                f"File: {file_model.relative_path}\n"
                f"Language: {file_model.language}\n"
                f"Element: module_block ({sym_name})\n"
                f"Lines: {start_line}-{end_line}\n"
            )
            contextual = f"{header}\n{raw_code}"
            content_hash = hashlib.sha256(contextual.encode("utf-8")).hexdigest()

            chunks.append(
                SmartCodeChunkDTO(
                    file_id=file_model.id,
                    symbol_id=None,
                    file_path=file_model.relative_path,
                    language=file_model.language,
                    class_name=None,
                    symbol_name=sym_name,
                    element_type="module_block",
                    signature=f"{file_model.relative_path}:{start_line}-{end_line}",
                    start_line=start_line,
                    end_line=end_line,
                    content_hash=content_hash,
                    contextual_content=contextual,
                    raw_code=raw_code,
                )
            )
            part += 1
        return chunks

    @staticmethod
    def _build_dto(
        file_model: RepositoryFileModel,
        symbol: CodeSymbolModel,
        start_line: int,
        end_line: int,
        code_lines: list[str],
        part_index: int | None,
    ) -> SmartCodeChunkDTO:
        raw_code = "\n".join(code_lines)
        sym_name = (
            f"{symbol.qualified_name} (part {part_index})"
            if part_index
            else symbol.qualified_name
        )
        doc_line = f"Documentation: {symbol.documentation}\n" if symbol.documentation else ""
        deps_line = (
            f"Calls/Dependencies: {', '.join(symbol.dependencies[:12])}\n"
            if symbol.dependencies
            else ""
        )
        header = (
            f"File: {file_model.relative_path}\n"
            f"Language: {file_model.language}\n"
            f"Element: {symbol.symbol_type.value} {sym_name}\n"
            f"Signature: {symbol.signature}\n"
            f"{doc_line}"
            f"{deps_line}"
            f"Lines: {start_line}-{end_line}\n"
        )
        contextual = f"{header}\n{raw_code}"
        content_hash = hashlib.sha256(contextual.encode("utf-8")).hexdigest()

        return SmartCodeChunkDTO(
            file_id=file_model.id,
            symbol_id=symbol.id,
            file_path=file_model.relative_path,
            language=file_model.language,
            class_name=symbol.parent_name
            or (symbol.name if symbol.symbol_type == SymbolType.CLASS else None),
            symbol_name=sym_name,
            element_type=symbol.symbol_type.value,
            signature=symbol.signature,
            start_line=start_line,
            end_line=end_line,
            content_hash=content_hash,
            contextual_content=contextual,
            raw_code=raw_code,
        )
