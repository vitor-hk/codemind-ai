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