# confluence-to-rag 📚→🤖 (work-in-progress!!)

Convert Confluence spaces and pages into RAG-optimized content for AI applications. This tool helps bridge the gap between Confluence documentation and AI by making your content queryable through RAG (Retrieval-Augmented Generation).

## Features ✨

- Extract content from Confluence including:
  - Full space content with all pages
  - Individual page content
  - Page metadata and versions
  - Content hierarchies
- Multiple output formats:
  - CSV for raw data
  - PDF for single pages
  - JSONL for RAG-optimized content
- Clean HTML content
- Process content for RAG compatibility
- Comprehensive error handling and logging
- Progress tracking and detailed reports

## Workflow Overview 🔄

```mermaid
flowchart LR
    subgraph Input ["1. Input"]
        C[Confluence Space/Page]
    end
    
    subgraph Process ["2. Processing"]
        E[Extract Content]
        H[Clean HTML]
        R[Convert to RAG]
    end
    
    subgraph Output ["3. Output"]
        CSV[CSV Files]
        PDF[PDF Files]
        J[JSONL Files]
    end
    
    C --> E
    E --> H
    H --> R
    R --> CSV
    R --> PDF
    R --> J
    
    style C fill:#ffffff,stroke:#000000,stroke-width:4px
    style E fill:#ffffff,stroke:#000000,stroke-width:2px,stroke-dasharray: 5 5
    style H fill:#ffffff,stroke:#000000,stroke-width:2px,stroke-dasharray: 10 5
    style R fill:#ffffff,stroke:#000000,stroke-width:2px,stroke-dasharray: 15 5
    style CSV fill:#ffffff,stroke:#000000,stroke-width:2px,pattern:dots
    style PDF fill:#ffffff,stroke:#000000,stroke-width:2px,pattern:grid
    style J fill:#ffffff,stroke:#000000,stroke-width:2px,pattern:grid
```

## System Architecture 🏗️

```mermaid
graph TB
    subgraph Interface ["User Interface"]
        CLI([Command Line Tool])
    end
    
    subgraph Core ["Core Processing"]
        direction LR
        Ext[["Confluence Extractor"]]
        Proc[["Content Processor"]]
    end
    
    subgraph External ["External Services"]
        direction LR
        CA[("Confluence API")]
    end
    
    subgraph Storage ["Data Storage"]
        Raw[("Raw CSV")]
        Processed[("JSONL")]
    end
    
    CLI --> Ext & Proc
    Ext --> CA
    CA --> Raw
    Raw --> Proc
    Proc --> Processed
    
    style CLI fill:#ffffff,stroke:#000000,stroke-width:4px
    style Ext fill:#ffffff,stroke:#000000,stroke-width:2px,pattern:dots
    style Proc fill:#ffffff,stroke:#000000,stroke-width:2px,pattern:grid
    style CA fill:#ffffff,stroke:#000000,stroke-width:2px,stroke-dasharray: 5 5
    style Raw fill:#ffffff,stroke:#000000,stroke-width:2px,pattern:cross
    style Processed fill:#ffffff,stroke:#000000,stroke-width:2px,pattern:cross
```

## Processing Steps 🔄

```mermaid
sequenceDiagram
    participant U as User
    participant C as CLI
    participant A as Confluence API
    participant S as Storage
    
    Note over U,S: 1️⃣ Content Extraction
    U->>C: Run extract command
    C->>A: Request content
    A-->>C: Return content
    C->>S: Save raw CSV
    
    Note over U,S: 2️⃣ Content Processing
    U->>C: Run process command
    C->>S: Load raw CSV
    C->>C: Clean content
    C->>S: Save RAG JSONL
```

## Output Structure 📊

```mermaid
graph TD
    subgraph "Output Directory Structure"
        Root(("📁 output/"))
        Data["📂 data/"]
        Logs["📂 logs/"]
        
        Root --> Data
        Root --> Logs
        
        Data --> |Raw Content| RC["📄 space_content.csv"]
        Data --> |Processed| PC["📄 processed_content.jsonl"]
        Data --> |Single Pages| SP["📄 page_123.pdf"]
        
        Logs --> |Extraction| EL["📝 extract_logs.log"]
        Logs --> |Processing| PL["📝 process_logs.log"]
    end
    
    style Root fill:#ffffff,stroke:#000000,stroke-width:4px
    style Data fill:#ffffff,stroke:#000000,stroke-width:2px,pattern:dots
    style Logs fill:#ffffff,stroke:#000000,stroke-width:2px,pattern:grid
```

## Installation 🚀

### Using Poetry

```bash
git clone https://github.com/yourusername/confluence-to-rag.git
cd confluence-to-rag
poetry install
```

## Setup 🔧

1. Get your Confluence access token:
   - Log in to Confluence
   - Go to Profile Settings
   - Navigate to Security
   - Generate an API token

2. Set environment variables:
```bash
export CONFLUENCE_URL='https://your-domain.atlassian.net'
export CONFLUENCE_USERNAME='your-email@domain.com'
export CONFLUENCE_API_TOKEN='your-api-token'
```

## Usage 💻

### Basic Workflow

1. **Extract a Confluence space**:
```bash
python main.py extract-space SPACENAME
```

2. **Extract a single page**:
```bash
python main.py extract-page PAGE_ID --format pdf
```

3. **Process extracted content to RAG format**:
```bash
python main.py process ./output/data/SPACENAME_content.csv
```

### Output Format 📄

The tool generates JSONL files with RAG-optimized content:

```json
{
  "content": "Clean text content without HTML markup",
  "metadata": {
    "id": "page_id",
    "title": "Page Title",
    "url": "https://confluence-url/pages/page-id",
    "version": "1",
    "last_modified": "2024-01-01T00:00:00.000Z",
    "source": "confluence"
  }
}
```

## Error Handling 🚨

The tool includes comprehensive error handling:
- API authentication issues
- Network connectivity problems
- HTML parsing errors
- Invalid content formats

Errors are logged to:
```
./output/logs/[command]_[timestamp].log
```

## Development 🛠️

### Setup

```bash
# Clone repository
git clone https://github.com/yourusername/confluence-to-rag.git
cd confluence-to-rag

# Install dependencies
poetry install

# Run with Poetry
poetry run python main.py extract-space SPACENAME
```

## Contributing 🤝

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## Troubleshooting 🔍

### Common Issues

1. **"No access token provided"**
   ```bash
   export CONFLUENCE_API_TOKEN='your_token_here'
   # or
   python main.py extract-space SPACENAME --api-token your_token_here
   ```

2. **Connection Issues**
   - Check your Confluence URL is correct
   - Verify your API token has correct permissions
   - Ensure you have network access to Confluence

3. **HTML Processing Issues**
   - Try extracting a single page first to verify content
   - Check if the page contains complex macros or embeds

## License 📝

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Support 💬

- 📫 For bugs and feature requests, please [open an issue](https://github.com/yourusername/confluence-to-rag/issues)
- 💡 For questions and discussions, please use [GitHub Discussions](https://github.com/yourusername/confluence-to-rag/discussions)

## Acknowledgments 🙏

- Atlassian Confluence API Documentation
- The open-source community
- BeautifulSoup4 for HTML processing
