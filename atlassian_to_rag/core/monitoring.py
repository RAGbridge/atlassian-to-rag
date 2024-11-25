import time
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

import psutil
from prometheus_client import Counter, Histogram, start_http_server


@dataclass
class MetricsConfig:
    enabled: bool = True
    port: int = 8000
    path: str = "/metrics"


class Metrics:
    def __init__(self, config: MetricsConfig):
        self.config = config
        if config.enabled:
            start_http_server(config.port)

        # Define metrics
        self.request_count = Counter(
            "confluence_requests_total",
            "Total number of requests made to Confluence",
            ["method", "status"],
        )

        self.request_latency = Histogram(
            "confluence_request_duration_seconds",
            "Request latency in seconds",
            ["method"],
        )

        self.processing_time = Histogram(
            "content_processing_duration_seconds",
            "Content processing time in seconds",
            ["operation"],
        )

        self.error_count = Counter("error_total", "Total number of errors", ["type"])

    def track_request(self, method: str, status: str) -> None:
        """Track a request to Confluence."""
        if self.config.enabled:
            self.request_count.labels(method=method, status=status).inc()

    def track_latency(self, method: str, duration: float) -> None:
        """Track request latency."""
        if self.config.enabled:
            self.request_latency.labels(method=method).observe(duration)

    def track_processing(self, operation: str, duration: float) -> None:
        """Track content processing time."""
        if self.config.enabled:
            self.processing_time.labels(operation=operation).observe(duration)

    def track_error(self, error_type: str) -> None:
        """Track an error."""
        if self.config.enabled:
            self.error_count.labels(type=error_type).inc()

    def get_system_metrics(self) -> Dict[str, float]:
        """Get system metrics."""
        return {
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_usage_percent": psutil.disk_usage("/").percent,
        }
