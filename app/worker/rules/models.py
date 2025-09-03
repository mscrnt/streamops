"""
Core models for the rule automation engine.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, Any, List


@dataclass
class Artifact:
    """Represents a file artifact in the processing pipeline."""
    path: Path
    mime: Optional[str] = None
    ext: Optional[str] = None     # e.g. ".mov"
    meta: Dict[str, Any] = field(default_factory=dict)   # duration, codec, etc.
    
    def __post_init__(self):
        """Ensure path is a Path object and derive extension if not provided."""
        if not isinstance(self.path, Path):
            self.path = Path(self.path)
        if self.ext is None and self.path.suffix:
            self.ext = self.path.suffix


@dataclass
class RuleContext:
    """Context carried through rule execution."""
    original: Artifact        # the file that triggered the rule
    active: Artifact          # the artifact subsequent actions operate on
    history: List[Artifact] = field(default_factory=list)  # prior actives
    vars: Dict[str, Any] = field(default_factory=dict)     # user/template vars
    
    def update_active(self, new_artifact: Artifact):
        """Update the active artifact and add the old one to history."""
        if self.active and self.active.path != new_artifact.path:
            self.history.append(self.active)
        self.active = new_artifact


@dataclass
class ActionResult:
    """Result from executing a rule action."""
    primary_output_path: Optional[Path] = None          # new file produced; None if no file
    outputs: Dict[str, Path] = field(default_factory=dict)  # optional additional outputs
    updated_vars: Dict[str, Any] = field(default_factory=dict)  # optional new vars to merge
    success: bool = True
    error: Optional[str] = None