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
from .jira import JiraExtractor, JiraProcessor

load_dotenv()
setup_logging()
logger = structlog.get_logger()

app = typer.Typer(help="Extract and process content from Confluence and JIRA")
console = Console()


def get_confluence_credentials() -> tuple[str, str, str]:
    """Get Confluence credentials from environment variables."""
    url = os.getenv("CONFLUENCE_URL")
    username = os.getenv("CONFLUENCE_USERNAME")
    token = os.getenv("CONFLUENCE_API_TOKEN")

    if not all([url, username, token]):
        raise ValueError("Missing required Confluence credentials in environment variables")

    return url, username, token


def get_jira_credentials() -> tuple[str, str, str]:
    """Get JIRA credentials from environment variables."""
    url = os.getenv("JIRA_URL")
    username = os.getenv("JIRA_USERNAME")
    token = os.getenv("JIRA_API_TOKEN")

    if not all([url, username, token]):
        raise ValueError("Missing required JIRA credentials in environment variables")

    return url, username, token


class Application:
    def __init__(self):
        # Initialize credentials
        self.confluence_url, self.confluence_username, self.confluence_token = get_confluence_credentials()
        self.jira_url, self.jira_username, self.jira_token = get_jira_credentials()

        # Initialize Redis connection
        redis_url = os.getenv("REDIS_URL")
        self.cache_manager = CacheManager(redis_url) if redis_url else None
        self.rate_limiter = RateLimiter(redis_url) if redis_url else None

        # Initialize metrics
        metrics_config = MetricsConfig(
            enabled=os.getenv("ENABLE_METRICS", "true").lower() == "true",
            port=int(os.getenv("METRICS_PORT", "8000"))
        )
        self.metrics = Metrics(metrics_config)

        # Initialize security
        security_config = SecurityConfig(
            jwt_secret=os.getenv("JWT_SECRET", "your-secret-key"),
            allowed_origins=os.getenv("ALLOWED_ORIGINS", "").split(",")
        )
        self.security = Security(security_config)

        # Initialize Confluence components
        self.confluence_extractor = ConfluenceExtractor(
            self.confluence_url,
            self.confluence_username,
            self.confluence_token,
            cache_manager=self.cache_manager,
            rate_limiter=self.rate_limiter,
            metrics=self.metrics
        )
        self.confluence_processor = ConfluenceProcessor(metrics=self.metrics)

        # Initialize JIRA components
        self.jira_extractor = JiraExtractor(
            self.jira_url,
            self.jira_username,
            self.jira_token,
            cache_manager=self.cache_manager,
            rate_limiter=self.rate_limiter,
            metrics=self.metrics
        )
        self.jira_processor = JiraProcessor(metrics=self.metrics)


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

            # Extract and process content
            pages = app_instance.confluence_extractor.get_space_content(space_key)
            processed_pages = []

            if format in ["raw", "all"]:
                progress.update(task, description="Saving raw content...")
                raw_output = output_path / f"{space_key}_raw.csv"
                pd.DataFrame(pages).to_csv(raw_output, index=False)

            if format in ["processed", "all"]:
                progress.update(task, description="Processing content...")
                for page in pages:
                    processed_page = app_instance.confluence_processor.process_page(page)
                    processed_pages.append(processed_page)

                processed_output = output_path / f"{space_key}_processed.jsonl"
                with open(processed_output, "w") as f:
                    for page in processed_pages:
                        f.write(json.dumps(page) + "\n")

            # Save summary
            summary = {
                "space_key": space_key,
                "total_pages": len(pages),
                "extraction_time": datetime.utcnow().isoformat(),
                "output_formats": format
            }

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
            page = app_instance.confluence_extractor.get_single_page(page_id)

            if include_attachments:
                progress.update(task, description="Fetching attachments...")
                page["attachments"] = app_instance.confluence_extractor.get_attachments(page_id)

            if include_comments:
                progress.update(task, description="Fetching comments...")
                page["comments"] = app_instance.confluence_extractor.get_comments(page_id)

            if format in ["raw", "all"]:
                progress.update(task, description="Saving raw content...")
                raw_output = output_path / f"page_{page_id}_raw.json"
                with open(raw_output, "w") as f:
                    json.dump(page, f, indent=2)

            if format in ["processed", "all"]:
                progress.update(task, description="Processing content...")
                processed_page = app_instance.confluence_processor.process_page(page)
                processed_output = output_path / f"page_{page_id}_processed.json"
                with open(processed_output, "w") as f:
                    json.dump(processed_page, f, indent=2)

            console.print(f"✅ Successfully processed page {page_id}")
            console.print(f"📁 Results saved to {output_path}")

    except Exception as e:
        logger.error("Failed to extract page", page_id=page_id, error=str(e))
        raise typer.Exit(1)


@app.command()
def extract_jira_project(
    project_key: str = typer.Argument(help="JIRA project key"),
    output_dir: str = typer.Option("output", help="Output directory"),
    max_results: int = typer.Option(1000, help="Maximum number of issues to extract"),
    format: str = typer.Option("all", help="Output format (raw, processed, all)"),
):
    """Extract and process all issues from a JIRA project."""
    try:
        app_instance = Application()
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
            task = progress.add_task("Extracting project content...", total=None)

            issues = app_instance.jira_extractor.get_project_issues(project_key, max_results)

            if format in ["raw", "all"]:
                progress.update(task, description="Saving raw content...")
                raw_output = output_path / f"{project_key}_raw.csv"
                pd.DataFrame(issues).to_csv(raw_output, index=False)

            if format in ["processed", "all"]:
                progress.update(task, description="Processing content...")
                processed_issues = []
                for issue in issues:
                    processed_issue = app_instance.jira_processor.process_issue(issue)
                    processed_issues.append(processed_issue)

                processed_output = output_path / f"{project_key}_processed.jsonl"
                with open(processed_output, "w") as f:
                    for issue in processed_issues:
                        f.write(json.dumps(issue) + "\n")

                # Generate and save summary
                summary = app_instance.jira_processor.generate_project_summary(processed_issues)
                summary_output = output_path / f"{project_key}_summary.json"
                with open(summary_output, "w") as f:
                    json.dump(summary, f, indent=2)

            console.print(f"✅ Successfully processed {len(issues)} issues")
            console.print(f"📁 Results saved to {output_path}")

    except Exception as e:
        logger.error("Failed to extract JIRA project", project_key=project_key, error=str(e))
        raise typer.Exit(1)


@app.command()
def extract_jira_issue(
    issue_key: str = typer.Argument(help="JIRA issue key"),
    output_dir: str = typer.Option("output", help="Output directory"),
    format: str = typer.Option("all", help="Output format (raw, processed, all)"),
    include_attachments: bool = typer.Option(True, help="Include issue attachments"),
    include_comments: bool = typer.Option(True, help="Include issue comments"),
):
    """Extract and process a single JIRA issue."""
    try:
        app_instance = Application()
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
            task = progress.add_task("Extracting issue content...", total=None)

            issue = app_instance.jira_extractor.get_single_issue(issue_key)

            if include_attachments:
                progress.update(task, description="Fetching attachments...")
                issue["attachments"] = app_instance.jira_extractor.get_issue_attachments(issue_key)

            if include_comments:
                progress.update(task, description="Fetching comments...")
                issue["comments"] = app_instance.jira_extractor.get_issue_comments(issue_key)

            if format in ["raw", "all"]:
                progress.update(task, description="Saving raw content...")
                raw_output = output_path / f"issue_{issue_key}_raw.json"
                with open(raw_output, "w") as f:
                    json.dump(issue, f, indent=2)

            if format in ["processed", "all"]:
                progress.update(task, description="Processing content...")
                processed_issue = app_instance.jira_processor.process_issue(issue)
                processed_output = output_path / f"issue_{issue_key}_processed.json"
                with open(processed_output, "w") as f:
                    json.dump(processed_issue, f, indent=2)

            console.print(f"✅ Successfully processed issue {issue_key}")
            console.print(f"📁 Results saved to {output_path}")

    except Exception as e:
        logger.error("Failed to extract JIRA issue", issue_key=issue_key, error=str(e))
        raise typer.Exit(1)


@app.command()
def analyze_sprint(
    project_key: str = typer.Argument(help="JIRA project key"),
    sprint_name: str = typer.Argument(help="Sprint name"),
    output_dir: str = typer.Option("output", help="Output directory"),
):
    """Analyze a sprint's issues and metrics."""
    try:
        app_instance = Application()
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
            task = progress.add_task("Analyzing sprint...", total=None)

            sprints = app_instance.jira_extractor.get_project_sprints(project_key)
            sprint = next((s for s in sprints if s["name"] == sprint_name), None)
            
            if not sprint:
                console.print(f"❌ Sprint '{sprint_name}' not found in project {project_key}")
                raise typer.Exit(1)

            sprint_issues = app_instance.jira_extractor.get_project_issues(
                project_key,
                f'sprint = "{sprint_name}"'
            )

            processed_issues = []
            for issue in sprint_issues:
                processed_issue = app_instance.jira_processor.process_issue(issue)
                processed_issues.append(processed_issue)

            summary = app_instance.jira_processor.generate_project_summary(processed_issues)
            metrics = app_instance.jira_processor.analyze_project_metrics(processed_issues)

            sprint_data = {
                "sprint_info": sprint,
                "summary": summary,
                "metrics": metrics,
                "issues": processed_issues
            }

            output_file = output_path / f"sprint_{project_key}_{sprint_name.replace(' ', '_')}.json"
            with open(output_file, "w") as f:
                json.dump(sprint_data, f, indent=2)

            console.print(f"✅ Successfully analyzed sprint '{sprint_name}'")
            console.print(f"📁 Results saved to {output_file}")

    except Exception as e:
        logger.error("Failed to analyze sprint", project_key=project_key, sprint_name=sprint_name, error=str(e))
        raise typer.Exit(1)


@app.command()
def batch_process(
    input_file: str = typer.Argument(help="Input file with page IDs, space keys, or JIRA keys"),
    output_dir: str = typer.Option("output", help="Output directory"),
    parallel: int = typer.Option(4, help="Number of parallel processes"),
    timeout: int = typer.Option(3600, help="Timeout in seconds"),
):
    """Process multiple pages, spaces, or JIRA items in parallel."""
    try:
        app_instance = Application()
        input_path = Path(input_file)
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        if not input_path.exists():
            raise typer.BadParameter(f"Input file not found: {input_path}")

        with open(input_path) as f:
            items = [line.strip() for line in f if line.strip()]

        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
            task = progress.add_task("Processing items...", total=len(items))

            results = {"successful": [], "failed": [], "start_time": datetime.utcnow().isoformat()}

            for item in items:
                try:
                    if item.startswith("SPACE_"):
                        app_instance.confluence_extractor.get_space_content(item[6:])
                    elif item.startswith("CONF_"):
                        app_instance.confluence_extractor.get_single_page(item[5:])
                    elif item.startswith("JIRA_"):
                        app_instance.jira_extractor.get_single_issue(item[5:])
                    elif item.startswith("PROJECT_"):
                        app_instance.jira_extractor.get_project_issues(item[8:])
                    else:
                        logger.warning(f"Unknown item type: {item}")
                        continue

                    results["successful"].append({"id": item, "timestamp": datetime.utcnow().isoformat()})
                except Exception as e:
                    results["failed"].append({"id": item, "error": str(e), "timestamp": datetime.utcnow().isoformat()})

                progress.advance(task)

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
