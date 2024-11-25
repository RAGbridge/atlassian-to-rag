from io import StringIO
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

    def _process_text(self, page: Dict[str, Any]) -> str:
        """Extract and clean main text content."""
        soup = BeautifulSoup(page.get("content", ""), "html.parser")

        # Remove unnecessary elements
        for element in soup.find_all(["script", "style"]):
            element.decompose()

        # Extract text with spacing
        text = soup.get_text(separator=" ", strip=True)

        # Clean and normalize text
        text = self.tag_pattern.sub("", text)
        text = " ".join(text.split())

        return text

    def process_page(self, page: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single page with all available processors."""
        try:
            start_time = datetime.now()

            processed_content = {}
            with ThreadPoolExecutor() as executor:
                futures = {
                    name: executor.submit(processor, page) 
                    for name, processor in self.content_processors.items()
                }

                for name, future in futures.items():
                    try:
                        processed_content[name] = future.result()
                    except Exception as e:
                        logger.warning(
                            "Failed to process content",
                            content_type=name,
                            page_id=page.get("id", "unknown"),
                            error=str(e),
                        )
                        # Set default values for failed processors
                        if name == "text":
                            processed_content[name] = ""
                        elif name == "metadata":
                            processed_content[name] = {}
                        else:
                            processed_content[name] = []

            # Combine all processed content with safe defaults
            result = {
                "content": processed_content.get("text", ""),
                "metadata": processed_content.get("metadata", {}),
                "tables": processed_content.get("tables", []),
                "code_blocks": processed_content.get("code", []),
                "attachments": processed_content.get("attachments", []),
                "comments": processed_content.get("comments", []),
            }

            # Calculate and store metrics
            processing_time = (datetime.now() - start_time).total_seconds()
            if self.metrics:
                self.metrics.track_processing("page", processing_time)

            return result

        except Exception as e:
            logger.error(
                "Failed to process page",
                page_id=page.get("id", "unknown"),
                error=str(e),
            )
            raise ProcessingError(
                f"Failed to process page: {str(e)}", 
                details={"page_id": page.get("id", "unknown")}
            )

    def _process_tables(self, page: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract tables from the content."""
        if not page.get("content"):
            return []

        soup = BeautifulSoup(page["content"], "html.parser")
        tables = []

        for table in soup.find_all("table"):
            try:
                # Convert table to string and wrap in StringIO
                html_string = StringIO(str(table))
                
                # Convert table to DataFrame
                df = pd.read_html(html_string)[0]

                # Convert DataFrame to dictionary
                table_dict = {
                    "headers": df.columns.tolist(),
                    "data": df.values.tolist(),
                    "shape": df.shape,
                }

                tables.append(table_dict)
            except Exception as e:
                logger.warning(
                    "Failed to process table",
                    page_id=page.get("id", "unknown"),
                    error=str(e),
                )

        return tables

    def _process_code(self, page: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract code blocks from the content."""
        if not page.get("content"):
            return []

        soup = BeautifulSoup(page["content"], "html.parser")
        code_blocks = []

        for code in soup.find_all(["code", "pre"]):
            language = code.get("class", ["text"])[0] if code.get("class") else "text"
            code_blocks.append({
                "language": language,
                "content": code.get_text(strip=True)
            })

        return code_blocks

    def _process_metadata(self, page: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and process page metadata."""
        return {
            "id": page.get("id", ""),
            "title": page.get("title", ""),
            "url": page.get("url", ""),
            "version": page.get("version", ""),
            "last_modified": page.get("last_modified", ""),
            "source": "confluence",
            "processed_at": datetime.utcnow().isoformat(),
        }

    def _process_attachments(self, page: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Process page attachments if present."""
        attachments = page.get("attachments", [])
        return [
            {
                "id": att.get("id", ""),
                "filename": att.get("filename", ""),
                "size": att.get("size", 0),
                "media_type": att.get("mediaType", ""),
            }
            for att in attachments
        ]

    def _process_comments(self, page: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Process page comments if present."""
        comments = page.get("comments", [])
        return [
            {
                "id": comment.get("id", ""),
                "author": comment.get("author", ""),
                "created": comment.get("created", ""),
                "content": self._process_text({"content": comment.get("content", "")}),
            }
            for comment in comments
        ]

    def save_as_pdf(self, processed_page: Dict[str, Any], output_path: Path):
        """Save processed content as PDF."""
        try:
            pdf = FPDF()
            pdf.add_page()

            # Add title
            pdf.set_font("Arial", "B", 16)
            title = processed_page.get("metadata", {}).get("title", "Untitled")
            pdf.cell(0, 10, title, ln=True)

            # Add metadata
            pdf.set_font("Arial", "I", 10)
            metadata = processed_page.get("metadata", {})
            pdf.cell(0, 10, f"Last modified: {metadata.get('last_modified', 'Unknown')}", ln=True)
            pdf.cell(0, 10, f"URL: {metadata.get('url', 'Unknown')}", ln=True)

            # Add content
            pdf.set_font("Arial", size=12)
            content = processed_page.get("content", "No content available")
            pdf.multi_cell(0, 10, content)

            # Add tables if present
            tables = processed_page.get("tables", [])
            if tables:
                pdf.add_page()
                pdf.set_font("Arial", "B", 14)
                pdf.cell(0, 10, "Tables", ln=True)

                for table in tables:
                    pdf.set_font("Arial", size=10)
                    for row in table.get("data", []):
                        pdf.cell(0, 10, " | ".join(map(str, row)), ln=True)

            pdf.output(str(output_path))

        except Exception as e:
            logger.error(
                "Failed to save PDF",
                error=str(e),
                output_path=str(output_path),
            )
            raise ProcessingError(f"Failed to save PDF: {str(e)}")

    def save_as_html(self, processed_page: Dict[str, Any], output_path: Path):
        """Save processed content as HTML."""
        try:
            metadata = processed_page.get("metadata", {})
            content = processed_page.get("content", "")

            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>{metadata.get("title", "Untitled")}</title>
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
                    <h1>{metadata.get("title", "Untitled")}</h1>
                    <p>Last modified: {metadata.get("last_modified", "Unknown")}</p>
                    <p>URL: <a href="{metadata.get("url", "#")}">{metadata.get("url", "Unknown")}</a></p>
                </div>

                <div class="content">
                    {content}
                </div>
            """

            # Add tables if present
            tables = processed_page.get("tables", [])
            if tables:
                html_content += '<div class="tables"><h2>Tables</h2>'
                for table in tables:
                    html_content += "<table><thead><tr>"
                    for header in table.get("headers", []):
                        html_content += f"<th>{header}</th>"
                    html_content += "</tr></thead><tbody>"
                    for row in table.get("data", []):
                        html_content += "<tr>"
                        for cell in row:
                            html_content += f"<td>{cell}</td>"
                        html_content += "</tr>"
                    html_content += "</tbody></table>"
                html_content += "</div>"

            # Add code blocks if present
            code_blocks = processed_page.get("code_blocks", [])
            if code_blocks:
                html_content += '<div class="code-blocks"><h2>Code Blocks</h2>'
                for code_block in code_blocks:
                    html_content += f"""
                    <div class="code-block">
                        <code class="language-{code_block.get('language', 'text')}">
                            {code_block.get('content', '')}
                        </code>
                    </div>
                    """
                html_content += "</div>"

            # Add comments if present
            comments = processed_page.get("comments", [])
            if comments:
                html_content += '<div class="comments"><h2>Comments</h2>'
                for comment in comments:
                    html_content += f"""
                    <div class="comment">
                        <p><strong>{comment.get('author', 'Unknown')}</strong> - {comment.get('created', 'Unknown')}</p>
                        <p>{comment.get('content', '')}</p>
                    </div>
                    """
                html_content += "</div>"

            html_content += """
            </body>
            </html>
            """

            with open(output_path, "w", encoding="utf-8") as f:
                f.write(html_content)

        except Exception as e:
            logger.error(
                "Failed to save HTML",
                error=str(e),
                output_path=str(output_path),
            )
            raise ProcessingError(f"Failed to save HTML: {str(e)}")

    def generate_summary(self, processed_pages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate a summary of processed content."""
        try:
            total_pages = len(processed_pages)
            if not total_pages:
                return {
                    "total_pages": 0,
                    "generated_at": datetime.utcnow().isoformat()
                }

            total_words = sum(len(page.get("content", "").split()) for page in processed_pages)
            total_tables = sum(len(page.get("tables", [])) for page in processed_pages)
            total_code_blocks = sum(len(page.get("code_blocks", [])) for page in processed_pages)
            total_comments = sum(len(page.get("comments", [])) for page in processed_pages)

            # Calculate averages
            avg_words = total_words / total_pages
            avg_tables = total_tables / total_pages
            avg_code_blocks = total_code_blocks / total_pages
            avg_comments = total_comments / total_pages

            # Find oldest and newest pages
            dates = [
                datetime.fromisoformat(page.get("metadata", {}).get("last_modified"))
                for page in processed_pages
                if page.get("metadata", {}).get("last_modified")
            ]

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
                    "oldest_page": min(dates).isoformat() if dates else None,
                    "newest_page": max(dates).isoformat() if dates else None,
                },
                "generated_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error("Failed to generate summary", error=str(e))
            raise ProcessingError(f"Failed to generate summary: {str(e)}")

    def generate_batch_summary(self, output_dir: Path) -> Dict[str, Any]:
        """Generate a summary for batch processing."""
        try:
            summary = {
                "total_files": 0,
                "successful_files": 0,
                "failed_files": 0,
                "file_types": {},
                "total_size": 0,
                "processing_errors": [],
            }

            # Scan output directory
            output_dir = Path(output_dir)
            if not output_dir.exists():
                return summary

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
                        try:
                            with open(file, "r", encoding="utf-8") as f:
                                error_content = f.read()
                                summary["processing_errors"].append({
                                    "file": str(file),
                                    "error": error_content
                                })
                        except Exception as e:
                            logger.warning(
                                "Failed to read error file",
                                file=str(file),
                                error=str(e)
                            )
                    else:
                        summary["successful_files"] += 1

            # Convert total size to readable format
            summary["total_size_readable"] = self._format_size(summary["total_size"])

            # Add timestamp
            summary["generated_at"] = datetime.utcnow().isoformat()

            return summary

        except Exception as e:
            logger.error("Failed to generate batch summary", error=str(e))
            raise ProcessingError(f"Failed to generate batch summary: {str(e)}")

    @staticmethod
    def _format_size(size: int) -> str:
        """Convert size in bytes to human readable format."""
        try:
            for unit in ["B", "KB", "MB", "GB"]:
                if size < 1024.0:
                    return f"{size:.2f} {unit}"
                size /= 1024.0
            return f"{size:.2f} TB"
        except Exception:
            return "0 B"

    def analyze_content_quality(self, processed_pages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze the quality of processed content."""
        try:
            quality_metrics = {
                "readability_scores": [],
                "content_completeness": [],
                "metadata_completeness": [],
                "formatting_quality": [],
            }

            if not processed_pages:
                return {
                    "averages": {
                        "readability": 0,
                        "content_completeness": 0,
                        "metadata_completeness": 0,
                        "formatting_quality": 0,
                    },
                    "ranges": {
                        "readability": (0, 0),
                        "content_completeness": (0, 0),
                        "metadata_completeness": (0, 0),
                        "formatting_quality": (0, 0),
                    },
                    "quality_score": 0,
                }

            for page in processed_pages:
                content = page.get("content", "")
                
                # Calculate readability score (simplified Flesch reading ease)
                words = len(content.split())
                sentences = len(re.split(r"[.!?]+", content))
                avg_words_per_sentence = words / max(sentences, 1)
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
                metadata = page.get("metadata", {})
                required_metadata = ["id", "title", "url", "version", "last_modified"]
                metadata_completeness = sum(1 for field in required_metadata if metadata.get(field)) / len(required_metadata)
                quality_metrics["metadata_completeness"].append(metadata_completeness * 100)

                # Calculate formatting quality
                formatting_indicators = [
                    "<h1>" in content,
                    "<h2>" in content,
                    "<p>" in content,
                    "<table>" in content,
                    "<code>" in content,
                ]
                formatting_quality = sum(1 for indicator in formatting_indicators if indicator) / len(formatting_indicators)
                quality_metrics["formatting_quality"].append(formatting_quality * 100)

            # Calculate overall statistics
            result = {
                "averages": {
                    "readability": float(np.mean(quality_metrics["readability_scores"])),
                    "content_completeness": float(np.mean(quality_metrics["content_completeness"])),
                    "metadata_completeness": float(np.mean(quality_metrics["metadata_completeness"])),
                    "formatting_quality": float(np.mean(quality_metrics["formatting_quality"])),
                },
                "ranges": {
                    "readability": (
                        float(min(quality_metrics["readability_scores"])),
                        float(max(quality_metrics["readability_scores"])),
                    ),
                    "content_completeness": (
                        float(min(quality_metrics["content_completeness"])),
                        float(max(quality_metrics["content_completeness"])),
                    ),
                    "metadata_completeness": (
                        float(min(quality_metrics["metadata_completeness"])),
                        float(max(quality_metrics["metadata_completeness"])),
                    ),
                    "formatting_quality": (
                        float(min(quality_metrics["formatting_quality"])),
                        float(max(quality_metrics["formatting_quality"])),
                    ),
                },
                "quality_score": float(np.mean([
                    np.mean(quality_metrics["readability_scores"]),
                    np.mean(quality_metrics["content_completeness"]),
                    np.mean(quality_metrics["metadata_completeness"]),
                    np.mean(quality_metrics["formatting_quality"]),
                ])),
            }

            return result

        except Exception as e:
            logger.error("Failed to analyze content quality", error=str(e))
            raise ProcessingError(f"Failed to analyze content quality: {str(e)}")
