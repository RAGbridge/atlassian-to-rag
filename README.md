# atlassian-to-rag 📚→🤖

Convert Confluence spaces/pages and JIRA projects/issues into RAG-optimized content for AI applications. This tool helps bridge the gap between Atlassian documentation and AI by making your content queryable through RAG (Retrieval-Augmented Generation).

## Features ✨

### Confluence Integration
- Extract content from Confluence including:
  - Full space content with all pages
  - Individual page content
  - Page metadata and versions
  - Content hierarchies
  - Attachments and comments

### JIRA Integration
- Extract and process JIRA data including:
  - Full project issues and metadata
  - Individual issue details
  - Sprint analysis and metrics
  - Issue attachments and comments
  - Change history and linked issues

### Output Formats
- Multiple output formats supported:
  - CSV for raw data
  - PDF for single items
  - JSONL for RAG-optimized content
  - HTML for web viewing
  - JSON for metrics and analysis

### Processing Features
- Clean HTML content
- Process content for RAG compatibility
- Generate summaries and analytics
- Track metrics and trends
- Comprehensive error handling and logging
- Progress tracking and detailed reports

## System Requirements 🛠️

- Python 3.9 or higher
- Poetry package manager
- Redis (optional, for caching)

## Installation 🚀

1. Clone the repository:
```bash
git clone https://github.com/yourusername/atlassian-to-rag.git
cd atlassian-to-rag
```

2. Install dependencies using Poetry:
```bash
poetry install
```

## Configuration ⚙️

### Confluence Setup
1. Get your Confluence access token:
   - Log in to Confluence
   - Go to Profile Settings → Security
   - Generate an API token

2. Set up Confluence environment variables:
```bash
export CONFLUENCE_URL='https://your-domain.atlassian.net/wiki'
export CONFLUENCE_USERNAME='your-email@domain.com'
export CONFLUENCE_API_TOKEN='your-api-token'
```

### JIRA Setup
1. Get your JIRA access token:
   - Log in to your Atlassian account
   - Go to Account Settings → Security
   - Create an API token

2. Set up JIRA environment variables:
```bash
export JIRA_URL='https://your-domain.atlassian.net'
export JIRA_USERNAME='your-email@domain.com'
export JIRA_API_TOKEN='your-api-token'
```

You can also create a `.env` file in the project root:
```env
# Confluence Settings
CONFLUENCE_URL='https://your-domain.atlassian.net/wiki'
CONFLUENCE_USERNAME='your-email@domain.com'
CONFLUENCE_API_TOKEN='your-token'

# JIRA Settings
JIRA_URL='https://your-domain.atlassian.net'
JIRA_USERNAME='your-email@domain.com'
JIRA_API_TOKEN='your-token'

# Optional Redis Settings
REDIS_URL='redis://localhost:6379'
```

## Usage 💻

### Confluence Commands

1. Extract a Confluence space:
```bash
poetry run atlassian-to-rag extract-space SPACENAME
```

2. Extract a single page:
```bash
poetry run atlassian-to-rag extract-page PAGE_ID --format pdf
```

### JIRA Commands

1. Extract a JIRA project:
```bash
poetry run atlassian-to-rag extract-jira-project PROJECT_KEY
```

2. Extract a single issue:
```bash
poetry run atlassian-to-rag extract-jira-issue ISSUE-123
```

3. Analyze sprint metrics:
```bash
poetry run atlassian-to-rag analyze-sprint PROJECT_KEY "Sprint 1"
```

### Additional Options

- Specify output directory:
```bash
poetry run atlassian-to-rag extract-space SPACENAME --output-dir /custom/path
```

- Choose output format:
```bash
# All formats
poetry run atlassian-to-rag extract-jira-project PROJECT_KEY --format all

# Only raw data
poetry run atlassian-to-rag extract-jira-project PROJECT_KEY --format raw

# Only processed data
poetry run atlassian-to-rag extract-jira-project PROJECT_KEY --format processed
```

- Include additional content:
```bash
poetry run atlassian-to-rag extract-jira-issue ISSUE-123 --include-attachments --include-comments
```

## Output Structure 📊

### Confluence Output
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

### JIRA Output
```json
{
  "content": "Clean issue description and comments",
  "metadata": {
    "key": "ISSUE-123",
    "title": "Issue Title",
    "type": "Bug",
    "status": "In Progress",
    "priority": "High",
    "assignee": "John Doe",
    "created": "2024-01-01T00:00:00.000Z",
    "updated": "2024-01-02T00:00:00.000Z"
  },
  "comments": [...],
  "changelog": [...],
  "linked_issues": [...]
}
```

## Development 🛠️

### Setup Development Environment

```bash
# Clone repository
git clone https://github.com/yourusername/atlassian-to-rag.git
cd atlassian-to-rag

# Install dependencies with dev packages
poetry install --with dev

# Install pre-commit hooks
poetry run pre-commit install

# Run tests
poetry run pytest

# Run linting
poetry run flake8
poetry run black .
poetry run mypy .
```

## Error Handling 🚨

The tool includes comprehensive error handling:
- API authentication issues
- Network connectivity problems
- Rate limiting and throttling
- Content processing errors
- Missing or malformed data

Errors are logged to:
```
./output/logs/[command]_[timestamp].log
```

## Troubleshooting 🔍

### Common Issues

1. **Authentication Errors**
   - Verify your API tokens are correct
   - Check your environment variables
   - Ensure you have the correct permissions

2. **Rate Limiting**
   - Use Redis for caching
   - Adjust batch sizes
   - Implement backoff strategies

3. **Missing Content**
   - Check user permissions
   - Verify content exists
   - Check for archived content

4. **Processing Errors**
   - Check log files for details
   - Verify content format
   - Handle special characters

## Contributing 🤝

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License 📝

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Support 💬

- 📫 For bugs and feature requests, please [open an issue](https://github.com/yourusername/atlassian-to-rag/issues)
- 💡 For questions and discussions, please use [GitHub Discussions](https://github.com/yourusername/atlassian-to-rag/discussions)

## Acknowledgments 🙏

- Atlassian API Documentation
- The open-source community
- BeautifulSoup4 for HTML processing
- All contributors to this project
