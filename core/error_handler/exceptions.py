class NoBackendError(RuntimeError):
    """Raised when no database backend (QuestDB or DuckDB) is available."""
    pass
