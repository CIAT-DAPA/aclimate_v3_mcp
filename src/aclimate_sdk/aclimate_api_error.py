from __future__ import annotations

class AClimateAPIError(Exception):
    """AClimate API v3 error"""
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        super().__init__(f"API error {status_code}: {detail}")
