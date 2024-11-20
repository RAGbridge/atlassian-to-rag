import typer
import pandas as pd
from atlassian import Confluence
from pathlib import Path
import logging
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from typing import Optional, List, Dict, Any
import csv
from fpdf import FPDF
import os
from dotenv import load_dotenv
from bs4 import BeautifulSoup
import re

# Load environment variables
load_dotenv()

app = typer.Typer(help="Extract and process content from Confluence")
console = Console()

def get_credentials(url: Optional[str] = None, username: Optional[str] = None, api_token: Optional[str] = None) -> tuple[str, str, str]:
    final_url = url or os.getenv('CONFLUENCE_URL')
    final_username = username or os.getenv('CONFLUENCE_USERNAME')
    final_token = api_token or os.getenv('CONFLUENCE_API_TOKEN')
    
    if not all([final_url, final_username, final_token]):
        raise typer.BadParameter(
            "Confluence credentials required via environment variables or command line arguments"
        )
    
    return final_url, final_username, final_token

class ConfluenceExtractor:
    def __init__(self, url: str, username: str, api_token: str):
        self.confluence = Confluence(
            url=url,
            username=username,
            password=api_token,
            cloud=True
        )
        self.base_url = url

    def get_space_content(self, space_key: str) -> List[Dict]:
        pages = []
        start = 0
        limit = 100
        
        while True:
            results = self.confluence.get_all_pages_from_space(
                space=space_key,
                start=start,
                limit=limit,
                expand='body.storage,version'
            )
            
            if not results:
                break
                
            for page in results:
                pages.append({
                    'id': page['id'],
                    'title': page['title'],
                    'content': page['body']['storage']['value'],
                    'url': f"{self.base_url}/wiki/spaces/{space_key}/pages/{page['id']}",
                    'version': page['version']['number'],
                    'last_modified': page['version']['when']
                })
            
            start += limit
            
        return pages

    def get_single_page(self, page_id: str) -> Dict:
        page = self.confluence.get_page_by_id(
            page_id=page_id,
            expand='body.storage,version'
        )
        
        return {
            'id': page['id'],
            'title': page['title'],
            'content': page['body']['storage']['value'],
            'url': f"{self.base_url}/wiki/pages/{page['id']}",
            'version': page['version']['number'],
            'last_modified': page['version']['when']
        }

    def save_to_csv(self, data: List[Dict], output_path: Path):
        df = pd.DataFrame(data)
        df.to_csv(output_path, index=False, quoting=csv.QUOTE_ALL)

    def save_to_pdf(self, data: Dict, output_path: Path):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(0, 10, data['title'], ln=True)
        pdf.set_font("Arial", size=12)
        pdf.multi_cell(0, 10, data['content'])
        pdf.output(str(output_path))

class ConfluenceProcessor:
    def __init__(self):
        self.tag_pattern = re.compile('<[^>]+>')

    def clean_html_content(self, content: str) -> str:
        soup = BeautifulSoup(content, 'html.parser')
        text = soup.get_text(separator=' ', strip=True)
        text = self.tag_pattern.sub('', text)
        text = ' '.join(text.split())
        return text

    def convert_to_rag(self, row: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "content": self.clean_html_content(row["content"]),
            "metadata": {
                "id": row["id"],
                "title": row["title"],
                "url": row["url"],
                "version": row["version"],
                "last_modified": row["last_modified"],
                "source": "confluence"
            }
        }

@app.command()
def extract_space(
    space_key: str = typer.Argument(..., help="Confluence space key"),
    url: Optional[str] = typer.Option(None, help="Confluence URL"),
    username: Optional[str] = typer.Option(None, help="Confluence username"),
    api_token: Optional[str] = typer.Option(None, help="Confluence API token"),
    output_dir: Path = typer.Option(Path("output"), help="Output directory")
):
    """Extract all pages from a Confluence space to CSV."""
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
            task = progress.add_task("Connecting to Confluence...", total=None)
            final_url, final_username, final_token = get_credentials(url, username, api_token)
            extractor = ConfluenceExtractor(final_url, final_username, final_token)
            
            progress.update(task, description="Extracting space content...")
            pages = extractor.get_space_content(space_key)
            
            progress.update(task, description="Saving to CSV...")
            output_file = output_dir / f"{space_key}_content.csv"
            extractor.save_to_csv(pages, output_file)
        
        console.print(f"✅ Successfully extracted {len(pages)} pages to {output_file}")
        
    except Exception as e:
        console.print(f"❌ Error: {str(e)}", style="red")
        raise typer.Exit(1)

@app.command()
def extract_page(
    page_id: str = typer.Argument(..., help="Confluence page ID"),
    url: Optional[str] = typer.Option(None, help="Confluence URL"),
    username: Optional[str] = typer.Option(None, help="Confluence username"),
    api_token: Optional[str] = typer.Option(None, help="Confluence API token"),
    output_dir: Path = typer.Option(Path("output"), help="Output directory"),
    format: str = typer.Option("csv", help="Output format (csv or pdf)")
):
    """Extract a single Confluence page to CSV or PDF."""
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
            task = progress.add_task("Connecting to Confluence...", total=None)
            final_url, final_username, final_token = get_credentials(url, username, api_token)
            extractor = ConfluenceExtractor(final_url, final_username, final_token)
            
            progress.update(task, description="Extracting page content...")
            page = extractor.get_single_page(page_id)
            
            progress.update(task, description=f"Saving to {format}...")
            output_file = output_dir / f"page_{page_id}.{format}"
            if format.lower() == "csv":
                extractor.save_to_csv([page], output_file)
            else:
                extractor.save_to_pdf(page, output_file)
        
        console.print(f"✅ Successfully extracted page to {output_file}")
        
    except Exception as e:
        console.print(f"❌ Error: {str(e)}", style="red")
        raise typer.Exit(1)

@app.command()
def process(
    input_file: Path = typer.Argument(..., help="Input CSV file from Confluence extraction"),
    output_dir: Path = typer.Option(Path("output"), help="Output directory"),
):
    """Process Confluence content to RAG format."""
    try:
        if not input_file.exists():
            raise typer.BadParameter(f"Input file not found: {input_file}")
            
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"processed_{input_file.stem}.jsonl"
        
        processor = ConfluenceProcessor()
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Reading input file...", total=None)
            df = pd.read_csv(input_file)
            
            progress.update(task, description="Processing content...")
            processed_docs = []
            for _, row in df.iterrows():
                doc = processor.convert_to_rag(row)
                processed_docs.append(doc)
            
            progress.update(task, description="Saving processed content...")
            df_processed = pd.DataFrame(processed_docs)
            df_processed.to_json(output_file, orient='records', lines=True)
        
        console.print(f"✅ Successfully processed {len(processed_docs)} documents to {output_file}")
        
    except Exception as e:
        console.print(f"❌ Error: {str(e)}", style="red")
        raise typer.Exit(1)

if __name__ == "__main__":
    app()