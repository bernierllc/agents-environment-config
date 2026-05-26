"""Canonical filesystem locations for org-config state.

All other org_config modules must go through OrgPaths rather than
hardcoding strings, so tests can inject tmp_path as home_dir.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class OrgPaths:
    home_dir: Path

    @classmethod
    def default(cls) -> "OrgPaths":
        return cls(home_dir=Path.home())

    @property
    def aec_dir(self) -> Path:
        return self.home_dir / ".aec"

    @property
    def orgs_dir(self) -> Path:
        return self.aec_dir / "orgs"

    @property
    def conflict_resolutions(self) -> Path:
        return self.aec_dir / "conflict-resolutions.json"

    @property
    def conflict_resolutions_history(self) -> Path:
        return self.aec_dir / "conflict-resolutions.history.json"

    @property
    def trusted_orgs(self) -> Path:
        return self.aec_dir / "trusted-orgs.json"

    @property
    def sources_dir(self) -> Path:
        """Cache root for cloned custom sources (Phase 4c)."""
        return self.aec_dir / "org-sources"

    def config_for(self, org_id: str) -> Path:
        return self.orgs_dir / f"{org_id}.yaml"

    def state_for(self, org_id: str) -> Path:
        return self.orgs_dir / f"{org_id}.state.json"

    def state_lock_for(self, org_id: str) -> Path:
        return self.orgs_dir / f"{org_id}.state.json.lock"
