FROM --platform=linux/amd64 python:3.13-slim

WORKDIR /app

# Install Node.js, npm, and system dependencies
RUN apt-get update && apt-get install -y curl && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    apt-get install -y \
        libreoffice \
        poppler-utils \
        pandoc \
        tesseract-ocr \
        fonts-nanum && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Install MCP packages globally
RUN npm install -g @modelcontextprotocol/server-filesystem

# PPT npm packages (global + local so require() works from any directory, including /tmp)
RUN npm install -g pptxgenjs sharp react react-dom react-icons docx && \
    mkdir -p /app/node_modules && \
    npm install --prefix /app pptxgenjs sharp react react-dom react-icons docx

# Allow require('pptxgenjs') to resolve from any working directory
ENV NODE_PATH=/usr/local/lib/node_modules:/app/node_modules

# Install Google Chrome (stable)
RUN curl -fsSL https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb -o /tmp/chrome.deb && \
    apt-get update && \
    apt-get install -y --no-install-recommends /tmp/chrome.deb && \
    rm /tmp/chrome.deb && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Install mcp-server-fetch-typescript and Playwright browsers
RUN npx -y mcp-server-fetch-typescript --version 2>/dev/null || true && \
    npx playwright install --with-deps chromium

# Install Python packages
RUN pip install fastapi python-multipart "uvicorn[standard]"
RUN pip install bedrock-agentcore aws-bedrock-token-generator
RUN pip install "boto3>=1.43.32" "botocore>=1.43.32" langchain_aws langchain langchain_community langchain-openai langchain-anthropic "openai>=2.41.0" "langgraph>=1.2.5" langgraph-checkpoint-sqlite "langgraph-supervisor>=0.0.31" "langgraph-swarm>=0.1.0" langchain-text-splitters
RUN pip install mcp "langchain-mcp-adapters>=0.3.0" httpx aiosqlite awslabs.aws-documentation-mcp-server
RUN pip install pandas numpy
RUN pip install tavily-python pytz
RUN pip install beautifulsoup4==4.12.3 plotly_express==0.4.1 matplotlib==3.10.0 
RUN pip install opensearch-py wikipedia requests
RUN pip install uv kaleido diagrams graphviz rich colorama finance-datareader PyPDF2 pyyaml
RUN pip install python-telegram-bot discord.py
RUN pip install python-pptx
# Skills: docx / xlsx / pptx / myslide
RUN pip install defusedxml lxml openpyxl Pillow pytesseract "markitdown[pptx]"
# Skills: pdf
RUN pip install reportlab pypdf pdfplumber PyYAML
# Skills: browser automation
RUN pip install "browser-use[cli]"

COPY . .

COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

EXPOSE 8501

HEALTHCHECK CMD curl --fail http://localhost:8501/api/health

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["uvicorn", "application.server:app", "--host", "0.0.0.0", "--port", "8501"]
