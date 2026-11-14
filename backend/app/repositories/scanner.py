import hashlib
from dataclasses import dataclass
from pathlib import Path
import pathspec

MAX_FILE_SIZE_BYTES = 1_048_576  # 1 MB limite por arquivo para evitar bundles/dumps

ALWAYS_IGNORED_DIRS: set[str] = {
    ".git",
    ".svn",
    ".hg",
    "node_modules",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".next",
    ".nuxt",
    ".vite",
    "dist",
    "build",
    "out",
    "target",
    "coverage",
    ".idea",
    ".vscode",
    "vendor",
}

SENSITIVE_FILE_PATTERNS: list[str] = [
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "*.p12",
    "*.pfx",
    "*.crt",
    "id_rsa",
    "id_dsa",
    "id_ed25519",
    "*credentials*.json",
    "*secret*.json",
    "*secret*.yaml",
    "*secret*.yml",
    ".npmrc",
    ".pypirc",
    "*.sqlite",
    "*.sqlite3",
    "*.db",
]

SAFE_ENV_TEMPLATES: set[str] = {".env.example", ".env.sample", ".env.template"}

LANGUAGE_BY_EXTENSION: dict[str, str] = {
    ".py": "Python",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".java": "Java",
    ".go": "Go",
    ".rs": "Rust",
    ".cpp": "C++",
    ".cc": "C++",
    ".c": "C",
    ".h": "C/C++ Header",
    ".cs": "C#",
    ".rb": "Ruby",
    ".php": "PHP",
    ".kt": "Kotlin",
    ".swift": "Swift",
    ".sql": "SQL",
    ".html": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".json": "JSON",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".toml": "TOML",
    ".md": "Markdown",
    ".sh": "Shell",
    ".dockerfile": "Dockerfile",
}

AST_SUPPORTED_LANGUAGES: set[str] = {"Python", "TypeScript", "JavaScript", "Java"}


@dataclass
class ScannedFileInfo:
    relative_path: str
    language: str
    extension: str
    size_bytes: int
    line_count: int
    content_hash: str
    is_ast_supported: bool


class RepositoryScanner:
    """Scanner determinístico e seguro de arquivos de código-fonte."""

    def __init__(self, root_path: Path, max_file_size: int = MAX_FILE_SIZE_BYTES) -> None:
        self.root_path = root_path.resolve()
        self.max_file_size = max_file_size
        self.gitignore_spec = self._load_gitignore()
        self.sensitive_spec = pathspec.PathSpec.from_lines(
            "gitignore", SENSITIVE_FILE_PATTERNS
        )

    def _load_gitignore(self) -> pathspec.PathSpec:
        gitignore_path = self.root_path / ".gitignore"
        patterns: list[str] = []
        if gitignore_path.is_file():
            try:
                patterns = gitignore_path.read_text(encoding="utf-8", errors="ignore").splitlines()
            except OSError:
                patterns = []
        return pathspec.PathSpec.from_lines("gitignore", patterns)

    def is_safe_subpath(self, target_path: Path) -> bool:
        """Previne Path Traversal e symlinks que apontam para fora do repositório."""
        try:
            resolved = target_path.resolve()
            return resolved.is_relative_to(self.root_path)
        except Exception:
            return False

    def should_ignore(self, relative_posix_path: str, file_name: str) -> bool:
        parts = relative_posix_path.split("/")
        if any(part in ALWAYS_IGNORED_DIRS for part in parts):
            return True

        if file_name not in SAFE_ENV_TEMPLATES:
            if self.sensitive_spec.match_file(relative_posix_path) or self.sensitive_spec.match_file(file_name):
                return True

        if self.gitignore_spec.match_file(relative_posix_path):
            return True

        return False

    @staticmethod
    def is_binary_bytes(sample: bytes) -> bool:
        return b"\x00" in sample

    @staticmethod
    def detect_language(file_path: Path) -> tuple[str | None, str]:
        if file_path.name.lower() == "dockerfile":
            return "Dockerfile", "dockerfile"
        ext = file_path.suffix.lower()
        lang = LANGUAGE_BY_EXTENSION.get(ext)
        return lang, ext

    def scan(self) -> list[ScannedFileInfo]:
        scanned_files: list[ScannedFileInfo] = []

        for path in sorted(self.root_path.rglob("*")):
            if path.is_symlink() or not path.is_file():
                continue

            if not self.is_safe_subpath(path):
                continue

            rel_posix = path.relative_to(self.root_path).as_posix()
            if self.should_ignore(rel_posix, path.name):
                continue

            lang, ext = self.detect_language(path)
            if not lang:
                continue

            try:
                stat = path.stat()
                if stat.st_size == 0 or stat.st_size > self.max_file_size:
                    continue

                raw_bytes = path.read_bytes()
                if self.is_binary_bytes(raw_bytes[:4096]):
                    continue

                content_hash = hashlib.sha256(raw_bytes).hexdigest()
                text_content = raw_bytes.decode("utf-8", errors="replace")
                line_count = len(text_content.splitlines())

                scanned_files.append(
                    ScannedFileInfo(
                        relative_path=rel_posix,
                        language=lang,
                        extension=ext,
                        size_bytes=stat.st_size,
                        line_count=line_count,
                        content_hash=content_hash,
                        is_ast_supported=lang in AST_SUPPORTED_LANGUAGES,
                    )
                )
            except OSError:
                continue

        return scanned_files
