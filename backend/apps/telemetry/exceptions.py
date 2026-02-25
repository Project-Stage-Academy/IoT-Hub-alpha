from typing import Any


class RawContractError(Exception):
    """Raised when telemetry.raw message contract is invalid."""

    def __init__(self, code: str, detail: Any):
        super().__init__(str(detail))
        self.code = code
        self.detail = detail
