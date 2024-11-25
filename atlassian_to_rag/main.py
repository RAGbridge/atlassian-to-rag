# atlassian_to_rag/main.py
import json
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import pandas as pd
import structlog
import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from .confluence import ConfluenceExtractor
from .core.cache import CacheManager
from .core.error_handling import ConfluenceAPIError, handle_errors
from .core.logging import setup_logging
from .core.monitoring import Metrics, MetricsConfig
from .core.rate_limiting import RateLimiter
from .core.security import Security, SecurityConfig
from .processor import ConfluenceProcessor

# Initialize logging
load_dotenv()
setup_logging()
logger = structlog.get_logger()

# Initialize Typer app and console
app = typer.Typer(help="Extract and process content from Confluence")
console = Console()


def get_credentials() -> tuple[str, str, str]:
    """Get Confluence credentials from environment variables."""
    url = os.getenv("CONFLUENCE_URL")
    username = os.getenv("CONFLUENCE_USERNAME")
    token = os.getenv("CONFLUENCE_API_TOKEN")

    if not all([url, username, token]):
        raise ValueError("Missing required Confluence credentials in environment variables")

    return url, username, token


class Application:
    def __init__(self):
        # Get Confluence credentials
        self.confluence_url, self.confluence_username, self.confluence_token = get_credentials()

        # Initialize Redis connection if available
        redis_url = os.getenv("REDIS_URL")
        self.cache_manager = CacheManager(redis_url) if redis_url else None
        self.rate_limiter = RateLimiter(redis_url) if redis_url else None

        # Initialize metrics
        metrics_config = MetricsConfig(enabled=os.getenv("ENABLE_METRICS", "true").lower() == "true", port=int(os.getenv("METRICS_PORT", "8000")))
        self.metrics = Metrics(metrics_config)

        # Initialize security
        security_config = SecurityConfig(jwt_secret=os.getenv("JWT_SECRET", "your-secret-key"), allowed_origins=os.getenv("ALLOWED_ORIGINS", "").split(","))
        self.security = Security(security_config)

        # Initialize main components
        self.extractor = ConfluenceExtractor(
            self.confluence_url, self.confluence_username, self.confluence_token, cache_manager=self.cache_manager, rate_limiter=self.rate_limiter, metrics=self.metrics
        )
        self.processor = ConfluenceProcessor(metrics=self.metrics)

    def process_space(self, space_key: str, output_dir: Path) -> None:
        """Process a Confluence space."""
        pages = self.extractor.get_space_content(space_key)
        processed_pages = []

        for page in pages:
            try:
                processed_page = self.processor.process_page(page)
                processed_pages.append(processed_page)
            except Exception as e:
                logger.error(f"Failed to process page: {page['id']}", error=str(e))
                continue

        # Save processed pages
        if processed_pages:
            output_file = output_dir / f"{space_key}_processed.jsonl"
            with open(output_file, "w") as f:
                for page in processed_pages:
                    f.write(json.dumps(page) + "\n")

    def process_page(self, page_id: str, output_dir: Path) -> None:
        """Process a single Confluence page."""
        page = self.extractor.get_single_page(page_id)
        processed_page = self.processor.process_page(page)

        output_file = output_dir / f"page_{page_id}_processed.json"
        with open(output_file, "w") as f:
            json.dump(processed_page, f, indent=2)


@app.command()
def extract_space(
    space_key: str = typer.Argument(help="Confluence space key"),
    output_dir: str = typer.Option("output", help="Output directory"),
    batch_size: int = typer.Option(100, help="Number of pages to process in each batch"),
    format: str = typer.Option("all", help="Output format (raw, processed, all)"),
):
    """Extract and process all pages from a Confluence space."""
    try:
        app_instance = Application()
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
            task = progress.add_task("Extracting space content...", total=None)

            # Extract content
            pages = app_instance.extractor.get_space_content(space_key)

            # Save raw content if requested
            if format in ["raw", "all"]:
                progress.update(task, description="Saving raw content...")
                raw_output = output_path / f"{space_key}_raw.csv"
                pd.DataFrame(pages).to_csv(raw_output, index=False)

            # Process and save content if requested
            if format in ["processed", "all"]:
                progress.update(task, description="Processing content...")
                app_instance.process_space(space_key, output_path)

            # Generate summary
            summary = {"space_key": space_key, "total_pages": len(pages), "extraction_time": datetime.utcnow().isoformat(), "output_formats": format}

            summary_file = output_path / f"{space_key}_summary.json"
            with open(summary_file, "w") as f:
                json.dump(summary, f, indent=2)

            console.print(f"✅ Successfully extracted {len(pages)} pages")
            console.print(f"📁 Results saved to {output_path}")

    except Exception as e:
        logger.error("Failed to extract space", space_key=space_key, error=str(e))
        raise typer.Exit(1)


@app.command()
def extract_page(
    page_id: str = typer.Argument(help="Confluence page ID"),
    output_dir: str = typer.Option("output", help="Output directory"),
    format: str = typer.Option("all", help="Output format (raw, processed, all)"),
    include_attachments: bool = typer.Option(True, help="Include page attachments"),
    include_comments: bool = typer.Option(True, help="Include page comments"),
):
    """Extract and process a single Confluence page."""
    try:
        app_instance = Application()
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
            task = progress.add_task("Extracting page content...", total=None)

            # Extract content
            page = app_instance.extractor.get_single_page(page_id)

            # Create a serializable copy of the page data
            page_data = {"id": page["id"], "title": page["title"], "content": page["content"], "version": page["version"]}

            # Get additional content if requested
            if include_attachments:
                progress.update(task, description="Fetching attachments...")
                page_data["attachments"] = app_instance.extractor.get_attachments(page_id)

            if include_comments:
                progress.update(task, description="Fetching comments...")
                page_data["comments"] = app_instance.extractor.get_comments(page_id)

            # Save raw content if requested
            if format in ["raw", "all"]:
                progress.update(task, description="Saving raw content...")
                raw_output = output_path / f"page_{page_id}_raw.json"
                with open(raw_output, "w") as f:
                    json.dump(page_data, f, indent=2)

            # Process and save content if requested
            if format in ["processed", "all"]:
                progress.update(task, description="Processing content...")
                app_instance.process_page(page_id, output_path)

            console.print(f"✅ Successfully processed page {page_id}")
            console.print(f"📁 Results saved to {output_path}")

    except Exception as e:
        logger.error("Failed to extract page", page_id=page_id, error=str(e))
        raise typer.Exit(1)


@app.command()
def batch_process(
    input_file: str = typer.Argument(help="Input file with page IDs or space keys"),
    output_dir: str = typer.Option("output", help="Output directory"),
    parallel: int = typer.Option(4, help="Number of parallel processes"),
    timeout: int = typer.Option(3600, help="Timeout in seconds"),
):
    """Process multiple pages or spaces in parallel."""
    try:
        app_instance = Application()
        input_path = Path(input_file)
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        if not input_path.exists():
            raise typer.BadParameter(f"Input file not found: {input_path}")

        # Read input file
        with open(input_path) as f:
            items = [line.strip() for line in f if line.strip()]

        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
            task = progress.add_task("Processing items...", total=len(items))

            results = {"successful": [], "failed": [], "start_time": datetime.utcnow().isoformat()}

            # Process items
            for item in items:
                try:
                    if item.startswith("SPACE_"):
                        app_instance.process_space(item[6:], output_path)
                    else:
                        app_instance.process_page(item, output_path)

                    results["successful"].append({"id": item, "timestamp": datetime.utcnow().isoformat()})
                except Exception as e:
                    results["failed"].append({"id": item, "error": str(e), "timestamp": datetime.utcnow().isoformat()})

                progress.advance(task)

            # Save results
            results_file = output_path / "batch_results.json"
            with open(results_file, "w") as f:
                json.dump(results, f, indent=2)

            console.print(f"✅ Successfully processed {len(results['successful'])} items")
            console.print(f"❌ Failed to process {len(results['failed'])} items")
            console.print(f"📁 Results saved to {output_path}")

    except Exception as e:
        logger.error("Failed to complete batch processing", error=str(e))
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
