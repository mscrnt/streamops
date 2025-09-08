"""StreamOps Job Processors

This module contains job processors for various media operations:
- RemuxJob: Remux media files to different container formats
- ProxyJob: Create proxy files for editing (DNxHR)
- TranscodeJob: Transcode with various presets
- IndexJob: Index assets in database with metadata
- MoveJob: Move files to target locations
- CopyJob: Copy files to target locations
"""

from .base import BaseJob
from .remux import RemuxJob
from .proxy import ProxyJob
from .transcode import TranscodeJob
from .index import IndexJob
from .move import MoveJob
from .copy import CopyJob

__all__ = [
    'BaseJob',
    'RemuxJob', 
    'ProxyJob',
    'TranscodeJob',
    'IndexJob',
    'MoveJob',
    'CopyJob'
]

# Job registry for easy lookup
JOB_REGISTRY = {
    'remux': RemuxJob,
    'proxy': ProxyJob,
    'transcode': TranscodeJob,
    'index': IndexJob,
    'move': MoveJob,
    'copy': CopyJob
}

def get_job_class(job_type: str) -> BaseJob:
    """Get job class by type name"""
    return JOB_REGISTRY.get(job_type)