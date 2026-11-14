from enum import StrEnum


class AnalysisStatus(StrEnum):
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class SourceType(StrEnum):
    GIT_URL = "GIT_URL"
    LOCAL_PATH = "LOCAL_PATH"
    ZIP_UPLOAD = "ZIP_UPLOAD"


class SymbolType(StrEnum):
    CLASS = "class"
    INTERFACE = "interface"
    FUNCTION = "function"
    METHOD = "method"
    CONSTRUCTOR = "constructor"


class RelationType(StrEnum):
    IMPORTS = "IMPORTS"
    CALLS = "CALLS"
    INHERITS = "INHERITS"
    IMPLEMENTS = "IMPLEMENTS"


class ConfidenceLevel(StrEnum):
    HIGH_AST = "HIGH_AST"
    MEDIUM_SCOPED = "MEDIUM_SCOPED"
    LOW_HEURISTIC = "LOW_HEURISTIC"
