"""StreamOps Job Processors

This module contains job processors for various media operations:
- RemuxJob: Remux media files to different container formats
- ThumbnailJob: Generate thumbnails, sprites, and hover previews
- ProxyJob: Create proxy files for editing (DNxHR)
- TranscodeJob: Transcode with various presets
- IndexJob: Index assets in database with metadata
"""

from .base import BaseJob
from .remux import RemuxJob
from .thumbnail import ThumbnailJob
from .proxy import ProxyJob
from .transcode import TranscodeJob
from .index import IndexJob

__all__ = [
    'BaseJob',
    'RemuxJob', 
    'ThumbnailJob',
    'ProxyJob',
    'TranscodeJob',
    'IndexJob'
]

# Job registry for easy lookup
JOB_REGISTRY = {
    'remux': RemuxJob,
    'thumbnail': ThumbnailJob,
    'proxy': ProxyJob,
    'transcode': TranscodeJob,
    'index': IndexJob
}

def get_job_class(job_type: str) -> BaseJob:
    """Get job class by type name"""
    return JOB_REGISTRY.get(job_type)