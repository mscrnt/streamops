"""
Template expansion for rule actions.
Single source of truth for all path templating.
"""
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
from .models import RuleContext


def expand_template(pattern: str, ctx: RuleContext) -> str:
    """
    Expand template pattern using the current active artifact.
    
    Available tokens:
    - {filename}: Full filename including extension (e.g., "2025-09-01 11-47-07.mov")
    - {stem}: Filename without extension (e.g., "2025-09-01 11-47-07")
    - {ext}: File extension including dot (e.g., ".mov")
    - {year}: Year from file modification time
    - {month}: Month from file modification time (zero-padded)
    - {day}: Day from file modification time (zero-padded)
    - Plus any custom variables in ctx.vars
    
    Args:
        pattern: Template pattern with {tokens}
        ctx: Rule context with active artifact
        
    Returns:
        Expanded string with tokens replaced
    """
    # ALWAYS derive from active artifact
    src = ctx.active.path
    
    # Get file modification time for date tokens
    try:
        dt = datetime.fromtimestamp(src.stat().st_mtime)
    except (OSError, ValueError):
        # Fallback to current time if file doesn't exist yet
        dt = datetime.now()
    
    # Build token dictionary
    tokens = {
        "filename": src.name,                     # "2025-09-01 11-47-07.mov"
        "stem": src.stem,                         # "2025-09-01 11-47-07"
        "ext": src.suffix,                        # ".mov"
        "year": f"{dt:%Y}",
        "month": f"{dt:%m}",
        "day": f"{dt:%d}",
        "hour": f"{dt:%H}",
        "minute": f"{dt:%M}",
        "second": f"{dt:%S}",
        **(ctx.vars or {})  # User-defined variables
    }
    
    # Replace tokens in pattern
    out = pattern
    for k, v in tokens.items():
        placeholder = "{" + k + "}"
        if placeholder in out:
            out = out.replace(placeholder, str(v))
    
    return out


def build_target_path(template: str, ctx: RuleContext) -> Path:
    """
    Build a target path from a template and context.
    
    Args:
        template: Path template with {tokens}
        ctx: Rule context
        
    Returns:
        Path object for the target
    """
    expanded = expand_template(template, ctx)
    return Path(expanded)