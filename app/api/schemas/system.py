"""System monitoring schemas"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Dict, Any, List, Optional


class CPUUsage(BaseModel):
    """CPU usage information"""
    percent: float = Field(..., description="CPU usage percentage")
    count: int = Field(..., description="Number of CPU cores")
    load_avg: List[float] = Field(..., description="Load average (1, 5, 15 minutes)")


class MemoryUsage(BaseModel):
    """Memory usage information"""
    total: int = Field(..., description="Total memory in bytes")
    available: int = Field(..., description="Available memory in bytes")
    percent: float = Field(..., description="Memory usage percentage")
    used: int = Field(..., description="Used memory in bytes")
    free: int = Field(..., description="Free memory in bytes")


class DiskUsage(BaseModel):
    """Disk usage information"""
    total: int = Field(..., description="Total disk space in bytes")
    used: int = Field(..., description="Used disk space in bytes")
    free: int = Field(..., description="Free disk space in bytes")
    percent: float = Field(..., description="Disk usage percentage")


class SystemStats(BaseModel):
    """System statistics"""
    cpu: CPUUsage
    memory: MemoryUsage
    disk: DiskUsage
    network: Dict[str, Any] = Field(..., description="Network I/O statistics")
    process: Dict[str, Any] = Field(..., description="Process statistics")
    timestamp: datetime = Field(..., description="Timestamp of stats collection")


class SystemHealth(BaseModel):
    """System health status"""
    status: str = Field(..., description="Overall health status (healthy, warning, critical, unhealthy)")
    checks: Dict[str, str] = Field(..., description="Individual component health checks")
    timestamp: datetime = Field(..., description="Timestamp of health check")


class ProcessInfo(BaseModel):
    """Process information"""
    pid: int = Field(..., description="Process ID")
    name: str = Field(..., description="Process name")
    cpu_percent: float = Field(..., description="CPU usage percentage")
    memory_percent: float = Field(..., description="Memory usage percentage")
    uptime: float = Field(..., description="Process uptime in seconds")
    type: str = Field(..., description="Process type (api, worker, other)")


class ResourceUsage(BaseModel):
    """Detailed resource usage"""
    cpu: Optional[Dict[str, Any]] = Field(None, description="CPU usage details")
    memory: Optional[Dict[str, Any]] = Field(None, description="Memory usage details")
    disk: Optional[Dict[str, Any]] = Field(None, description="Disk usage details")
    gpu: Optional[List[Dict[str, Any]]] = Field(None, description="GPU usage details")
    timestamp: datetime = Field(..., description="Timestamp of measurement")