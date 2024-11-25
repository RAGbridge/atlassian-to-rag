import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import structlog
from bs4 import BeautifulSoup
from fpdf import FPDF

from .core.error_handling import ProcessingError

logger = structlog.get_logger()


class ConfluenceProcessor:
    def __init__(self, metrics):
        self.metrics = metrics
        self.tag_pattern = re.compile("<[^>]+>")
        self._setup_processors()

    def _setup_processors(self):
        """Setup content processors and extractors."""
        self.content_processors = {
            "text": self._process_text,
            "tables": self._process_tables,
            "code": self._process_code,
            "metadata": self._process_metadata,
            "attachments": self._process_attachments,
            "comments": self._process_comments,
        }

    def process_page(self, page: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single page with all available processors."""
        try:
            start_time = datetime.now()

            processed_content = {}
            with ThreadPoolExecutor() as executor:
                futures = {name: executor.submit(processor, page) for name, processor in self.content_processors.items()}

                for name, future in futures.items():
                    try:
                        processed_content[name] = future.result()
                    except Exception as e:
                        logger.warning(
                            f"Failed to process {name}",
                            page_id=page["id"],
                            error=str(e),
                        )

            # Combine all processed content
            result = {
                "content": processed_content["text"],
                "metadata": processed_content["metadata"],
                "tables": processed_content["tables"],
                "code_blocks": processed_content["code"],
                "attachments": processed_content["attachments"],
                "comments": processed_content["comments"],
            }

            # Calculate and store metrics
            processing_time = (datetime.now() - start_time).total_seconds()
            self.metrics.track_processing("page", processing_time)

            return result

        except Exception as e:
            raise ProcessingError(f"Failed to process page: {str(e)}", details={"page_id": page["id"]})

    def _process_text(self, page: Dict[str, Any]) -> str:
        """Extract and clean main text content."""
        soup = BeautifulSoup(page["content"], "html.parser")

        # Remove unnecessary elements
        for element in soup.find_all(["script", "style"]):
            element.decompose()

        # Extract text with spacing
        text = soup.get_text(separator=" ", strip=True)

        # Clean and normalize text
        text = self.tag_pattern.sub("", text)
        text = " ".join(text.split())

        return text

    def _process_tables(self, page: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract tables from the content."""
        soup = BeautifulSoup(page["content"], "html.parser")
        tables = []

        for table in soup.find_all("table"):
            try:
                # Convert table to DataFrame
                df = pd.read_html(str(table))[0]

                # Convert DataFrame to dictionary
                table_dict = {
                    "headers": df.columns.tolist(),
                    "data": df.values.tolist(),
                    "shape": df.shape,
                }

                tables.append(table_dict)
            except Exception as e:
                logger.warning("Failed to process table", page_id=page["id"], error=str(e))

        return tables

    def _process_code(self, page: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract code blocks from the content."""
        soup = BeautifulSoup(page["content"], "html.parser")
        code_blocks = []

        for code in soup.find_all(["code", "pre"]):
            language = code.get("class", ["text"])[0]
            code_blocks.append({"language": language, "content": code.get_text()})

        return code_blocks

    def _process_metadata(self, page: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and process page metadata."""
        return {
            "id": page["id"],
            "title": page["title"],
            "url": page["url"],
            "version": page["version"],
            "last_modified": page["last_modified"],
            "source": "confluence",
            "processed_at": datetime.utcnow().isoformat(),
        }

    def _process_attachments(self, page: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Process page attachments if present."""
        attachments = page.get("attachments", [])
        return [
            {
                "id": att["id"],
                "filename": att["filename"],
                "size": att["size"],
                "media_type": att["mediaType"],
            }
            for att in attachments
        ]

    def _process_comments(self, page: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Process page comments if present."""
        comments = page.get("comments", [])
        return [
            {
                "id": comment["id"],
                "author": comment["author"],
                "created": comment["created"],
                "content": self._process_text({"content": comment["content"]}),
            }
            for comment in comments
        ]

    def save_as_pdf(self, processed_page: Dict[str, Any], output_path: Path):
        """Save processed content as PDF."""
        pdf = FPDF()
        pdf.add_page()

        # Add title
        pdf.set_font("Arial", "B", 16)
        pdf.cell(0, 10, processed_page["metadata"]["title"], ln=True)

        # Add metadata
        pdf.set_font("Arial", "I", 10)
        pdf.cell(
            0,
            10,
            f"Last modified: {processed_page['metadata']['last_modified']}",
            ln=True,
        )
        pdf.cell(0, 10, f"URL: {processed_page['metadata']['url']}", ln=True)

        # Add content
        pdf.set_font("Arial", size=12)
        pdf.multi_cell(0, 10, processed_page["content"])

        # Add tables if present
        if processed_page["tables"]:
            pdf.add_page()
            pdf.set_font("Arial", "B", 14)
            pdf.cell(0, 10, "Tables", ln=True)

            for table in processed_page["tables"]:
                pdf.set_font("Arial", size=10)
                for row in table["data"]:
                    pdf.cell(0, 10, " | ".join(map(str, row)), ln=True)

        pdf.output(str(output_path))

    def save_as_html(self, processed_page: Dict[str, Any], output_path: Path):
        """Save processed content as HTML."""
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{processed_page['            metadata']['title']}</title>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; margin: 2rem; }}
                .metadata {{ background: #f5f5f5; padding: 1rem; margin-bottom: 1rem; }}
                .content {{ margin-bottom: 2rem; }}
                .tables {{ margin-top: 2rem; }}
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                .code-block {{ background: #f8f8f8; padding: 1rem; margin: 1rem 0; }}
                .comments {{ margin-top: 2rem; border-top: 1px solid #ddd; }}
                .comment {{ margin: 1rem 0; padding: 1rem; background: #f9f9f9; }}
            </style>
        </head>
        <body>
            <div class="metadata">
                <h1>{processed_page['metadata']['title']}</h1>
                <p>Last modified: {processed_page['metadata']['last_modified']}</p>
                <p>URL: <a href="{processed_page['metadata']['url']}">{processed_page['metadata']['url']}</a></p>
            </div>

            <div class="content">
                {processed_page['content']}
            </div>
        """

        # Add tables if present
        if processed_page["tables"]:
            html_content += '<div class="tables"><h2>Tables</h2>'
            for table in processed_page["tables"]:
                html_content += "<table><thead><tr>"
                for header in table["headers"]:
                    html_content += f"<th>{header}</th>"
                html_content += "</tr></thead><tbody>"
                for row in table["data"]:
                    html_content += "<tr>"
                    for cell in row:
                        html_content += f"<td>{cell}</td>"
                    html_content += "</tr>"
                html_content += "</tbody></table>"
            html_content += "</div>"

        # Add code blocks if present
        if processed_page["code_blocks"]:
            html_content += '<div class="code-blocks"><h2>Code Blocks</h2>'
            for code_block in processed_page["code_blocks"]:
                html_content += f"""
                <div class="code-block">
                    <code class="language-{code_block['language']}">
                        {code_block['content']}
                    </code>
                </div>
                """
            html_content += "</div>"

        # Add comments if present
        if processed_page["comments"]:
            html_content += '<div class="comments"><h2>Comments</h2>'
            for comment in processed_page["comments"]:
                html_content += f"""
                <div class="comment">
                    <p><strong>{comment['author']}</strong> - {comment['created']}</p>
                    <p>{comment['content']}</p>
                </div>
                """
            html_content += "</div>"

        html_content += """
        </body>
        </html>
        """

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)

    def generate_summary(self, processed_pages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate a summary of processed content."""
        total_pages = len(processed_pages)
        total_words = sum(len(page["content"].split()) for page in processed_pages)
        total_tables = sum(len(page["tables"]) for page in processed_pages)
        total_code_blocks = sum(len(page["code_blocks"]) for page in processed_pages)
        total_comments = sum(len(page["comments"]) for page in processed_pages)

        # Calculate averages
        avg_words = total_words / total_pages if total_pages > 0 else 0
        avg_tables = total_tables / total_pages if total_pages > 0 else 0
        avg_code_blocks = total_code_blocks / total_pages if total_pages > 0 else 0
        avg_comments = total_comments / total_pages if total_pages > 0 else 0

        # Find oldest and newest pages
        dates = [datetime.fromisoformat(page["metadata"]["last_modified"]) for page in processed_pages]
        oldest_page = min(dates) if dates else None
        newest_page = max(dates) if dates else None

        return {
            "total_pages": total_pages,
            "total_words": total_words,
            "total_tables": total_tables,
            "total_code_blocks": total_code_blocks,
            "total_comments": total_comments,
            "averages": {
                "words_per_page": round(avg_words, 2),
                "tables_per_page": round(avg_tables, 2),
                "code_blocks_per_page": round(avg_code_blocks, 2),
                "comments_per_page": round(avg_comments, 2),
            },
            "date_range": {
                "oldest_page": oldest_page.isoformat() if oldest_page else None,
                "newest_page": newest_page.isoformat() if newest_page else None,
            },
            "generated_at": datetime.utcnow().isoformat(),
        }

    def generate_batch_summary(self, output_dir: Path) -> Dict[str, Any]:
        """Generate a summary for batch processing."""
        summary = {
            "total_files": 0,
            "successful_files": 0,
            "failed_files": 0,
            "file_types": {},
            "total_size": 0,
            "processing_errors": [],
        }

        # Scan output directory
        for file in output_dir.glob("**/*"):
            if file.is_file():
                summary["total_files"] += 1
                ext = file.suffix.lower()

                # Count file types
                summary["file_types"][ext] = summary["file_types"].get(ext, 0) + 1

                # Calculate total size
                summary["total_size"] += file.stat().st_size

                # Check for error indicators
                if "_error" in file.name:
                    summary["failed_files"] += 1
                    with open(file, "r") as f:
                        error_content = f.read()
                        summary["processing_errors"].append({"file": str(file), "error": error_content})
                else:
                    summary["successful_files"] += 1

        # Convert total size to readable format
        summary["total_size_readable"] = self._format_size(summary["total_size"])

        # Add timestamp
        summary["generated_at"] = datetime.utcnow().isoformat()

        return summary

    @staticmethod
    def _format_size(size: int) -> str:
        """Convert size in bytes to human readable format."""
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} TB"

    def analyze_content_quality(self, processed_pages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze the quality of processed content."""
        quality_metrics = {
            "readability_scores": [],
            "content_completeness": [],
            "metadata_completeness": [],
            "formatting_quality": [],
        }

        for page in processed_pages:
            # Calculate readability score (simplified Flesch reading ease)
            words = len(page["content"].split())
            sentences = len(re.split(r"[.!?]+", page["content"]))
            avg_words_per_sentence = words / sentences if sentences > 0 else 0
            readability_score = max(0, min(100, 206.835 - 1.015 * avg_words_per_sentence))
            quality_metrics["readability_scores"].append(readability_score)

            # Calculate content completeness
            required_fields = [
                "content",
                "metadata",
                "tables",
                "code_blocks",
                "comments",
            ]
            completeness = sum(1 for field in required_fields if page.get(field)) / len(required_fields)
            quality_metrics["content_completeness"].append(completeness * 100)

            # Calculate metadata completeness
            required_metadata = ["id", "title", "url", "version", "last_modified"]
            metadata_completeness = sum(1 for field in required_metadata if page["metadata"].get(field)) / len(required_metadata)
            quality_metrics["metadata_completeness"].append(metadata_completeness * 100)

            # Calculate formatting quality
            formatting_indicators = [
                "<h1>" in page["content"],
                "<h2>" in page["content"],
                "<p>" in page["content"],
                "<table>" in page["content"],
                "<code>" in page["content"],
            ]
            formatting_quality = sum(1 for indicator in formatting_indicators if indicator) / len(formatting_indicators)
            quality_metrics["formatting_quality"].append(formatting_quality * 100)

        # Calculate overall statistics
        return {
            "averages": {
                "readability": np.mean(quality_metrics["readability_scores"]),
                "content_completeness": np.mean(quality_metrics["content_completeness"]),
                "metadata_completeness": np.mean(quality_metrics["metadata_completeness"]),
                "formatting_quality": np.mean(quality_metrics["formatting_quality"]),
            },
            "ranges": {
                "readability": (
                    min(quality_metrics["readability_scores"]),
                    max(quality_metrics["readability_scores"]),
                ),
                "content_completeness": (
                    min(quality_metrics["content_completeness"]),
                    max(quality_metrics["content_completeness"]),
                ),
                "metadata_completeness": (
                    min(quality_metrics["metadata_completeness"]),
                    max(quality_metrics["metadata_completeness"]),
                ),
                "formatting_quality": (
                    min(quality_metrics["formatting_quality"]),
                    max(quality_metrics["formatting_quality"]),
                ),
            },
            "quality_score": np.mean(
                [
                    np.mean(quality_metrics["readability_scores"]),
                    np.mean(quality_metrics["content_completeness"]),
                    np.mean(quality_metrics["metadata_completeness"]),
                    np.mean(quality_metrics["formatting_quality"]),
                ]
            ),
        }
