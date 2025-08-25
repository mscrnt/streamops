from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from enum import Enum


class ReportType(str, Enum):
    """Report type enumeration"""
    weekly_summary = "weekly_summary"
    asset_summary = "asset_summary"
    job_performance = "job_performance"
    system_utilization = "system_utilization"
    rule_execution = "rule_execution"
    overlay_analytics = "overlay_analytics"
    error_summary = "error_summary"
    storage_usage = "storage_usage"


class ReportFormat(str, Enum):
    """Report output format"""
    json = "json"
    html = "html"
    pdf = "pdf"
    csv = "csv"


class ReportPeriod(str, Enum):
    """Report time period"""
    day = "day"
    week = "week"
    month = "month"
    quarter = "quarter"
    year = "year"
    custom = "custom"


class ReportMetric(BaseModel):
    """Individual report metric"""
    name: str = Field(..., description="Metric name")
    value: Any = Field(..., description="Metric value")
    unit: Optional[str] = Field(None, description="Metric unit")
    change: Optional[float] = Field(None, description="Change from previous period (%)")
    trend: Optional[str] = Field(None, description="Trend indicator (up/down/stable)")


class ReportChart(BaseModel):
    """Chart data for reports"""
    chart_type: str = Field(..., description="Chart type (line/bar/pie/area)")
    title: str = Field(..., description="Chart title")
    labels: List[str] = Field(..., description="Chart labels")
    datasets: List[Dict[str, Any]] = Field(..., description="Chart datasets")
    options: Optional[Dict[str, Any]] = Field(None, description="Chart options")


class ReportGenerate(BaseModel):
    """Generate report request"""
    report_type: ReportType = Field(..., description="Type of report to generate")
    format: ReportFormat = Field(ReportFormat.json, description="Output format")
    period: ReportPeriod = Field(ReportPeriod.week, description="Time period")
    start_date: Optional[date] = Field(None, description="Start date (for custom period)")
    end_date: Optional[date] = Field(None, description="End date (for custom period)")
    filters: Optional[Dict[str, Any]] = Field(None, description="Additional filters")
    include_charts: bool = Field(True, description="Whether to include charts")


class ReportResponse(BaseModel):
    """Report response"""
    id: str
    report_type: ReportType
    format: ReportFormat
    period: ReportPeriod
    start_date: date
    end_date: date
    generated_at: datetime
    file_path: Optional[str] = None
    download_url: Optional[str] = None
    size_bytes: Optional[int] = None
    expires_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class ReportData(BaseModel):
    """Report data content"""
    title: str = Field(..., description="Report title")
    subtitle: Optional[str] = Field(None, description="Report subtitle")
    period_description: str = Field(..., description="Period description")
    generated_at: datetime = Field(..., description="Generation timestamp")
    summary: List[ReportMetric] = Field(..., description="Summary metrics")
    sections: List[Dict[str, Any]] = Field(..., description="Report sections")
    charts: Optional[List[ReportChart]] = Field(None, description="Report charts")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class ReportListResponse(BaseModel):
    """Report list response"""
    reports: List[ReportResponse]
    total: int
    page: int
    per_page: int


class ReportSearchQuery(BaseModel):
    """Report search query"""
    report_type: Optional[ReportType] = Field(None, description="Filter by report type")
    format: Optional[ReportFormat] = Field(None, description="Filter by format")
    period: Optional[ReportPeriod] = Field(None, description="Filter by period")
    generated_after: Optional[datetime] = Field(None, description="Generated after timestamp")
    generated_before: Optional[datetime] = Field(None, description="Generated before timestamp")


class WeeklySummaryReport(BaseModel):
    """Weekly summary report data"""
    week_start: date
    week_end: date
    total_assets: int
    new_assets: int
    processed_jobs: int
    failed_jobs: int
    storage_used: int
    storage_freed: int
    top_sessions: List[Dict[str, Any]]
    asset_breakdown: Dict[str, int]
    job_breakdown: Dict[str, int]
    performance_metrics: Dict[str, float]


class AssetSummaryReport(BaseModel):
    """Asset summary report data"""
    total_assets: int
    by_type: Dict[str, int]
    by_status: Dict[str, int]
    by_session: Dict[str, int]
    storage_usage: Dict[str, int]
    processing_times: Dict[str, float]
    recent_assets: List[Dict[str, Any]]


class JobPerformanceReport(BaseModel):
    """Job performance report data"""
    total_jobs: int
    by_status: Dict[str, int]
    by_type: Dict[str, int]
    average_duration: Dict[str, float]
    success_rate: Dict[str, float]
    error_analysis: List[Dict[str, Any]]
    queue_metrics: Dict[str, float]


class SystemUtilizationReport(BaseModel):
    """System utilization report data"""
    cpu_usage: Dict[str, float]
    memory_usage: Dict[str, float]
    disk_usage: Dict[str, float]
    gpu_usage: Optional[Dict[str, float]] = None
    network_usage: Optional[Dict[str, float]] = None
    peak_usage_times: List[datetime]
    resource_alerts: List[Dict[str, Any]]