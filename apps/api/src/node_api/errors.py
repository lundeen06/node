"""Domain errors referenced by library docstrings (no solver implementations yet)."""


class NodeLibraryError(Exception):
    """Base class for recoverable library failures."""


class InfeasibleProblemError(NodeLibraryError):
    """Raised when no solution exists within stated constraints (e.g. Δv cap, Pc target)."""


class DataUnavailableError(NodeLibraryError):
    """Raised when upstream data (TLE, CDM, weather) is missing or stale."""


class FrameMismatchError(NodeLibraryError):
    """Raised when operands require a frame/time alignment that was not performed."""
