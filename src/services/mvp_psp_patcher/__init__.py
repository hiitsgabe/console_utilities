"""MVP Baseball PSP Patcher service.

Fetches MLB roster data and patches MVP Baseball (PSP, ULUS-10012)
ISO with updated player names, stats, and attributes.
"""

from services.mvp_psp_patcher.patcher import MVPPSPPatcher

__all__ = ["MVPPSPPatcher"]
