# 🔐 Exposed Credential Analysis Chat Interface

## Overview
Interactive chat application for analyzing exposed credentials and managing password reset workflows.

## Features
- 📂 **Dynamic File Upload**: Upload your current batch and master data Excel sheets
- 💬 **Chat Interface**: Ask questions about the data with follow-up support
- 📊 **Smart Analysis**: Uses Ollama (local LLM) to understand queries and provide insights
- 📥 **Excel Download**: Download password reset candidates as Excel files

## Quick Start

### Prerequisites
1. **Ollama running** (keep it open in a terminal):
```powershell
ollama serve
```

2. **Install dependencies**:
```powershell
pip install -r requirements.txt
```

### Run the Chat App
```powershell
streamlit run chat_app.py
```

This will open the app in your browser at `http://localhost:8501`

## How to Use

### Step 1: Upload Files
- Click in the sidebar (left panel)
- Upload your `current_batch.xlsx` file
- Upload your `master_data.xlsx` file
- Wait for "✅ Files loaded successfully!" message

### Step 2: Ask Questions
Type your question in the chat box. Examples:
- "How many users need password reset?"
- "List all users who need password reset"
- "Show me recently exposed users"
- "What's the exposure breakdown by source?"

### Step 3: Download Results
- When asking about password resets, a download button appears
- Click "📥 Download Password Reset Candidates" to get an Excel file
- Use this for your password reset workflow

### Step 4: Follow-up Questions
- The chat maintains conversation history
- Ask follow-up questions related to the data
- Clear history anytime with the "🔄 Clear Chat History" button

## Query Examples

| Question | Output |
|----------|--------|
| "How many users need password reset?" | Count + AI analysis |
| "List password reset candidates" | Full list + downloadable Excel |
| "Recently exposed users" | Count of users exposed in last 6 months |
| "Exposure breakdown by source" | Chart showing exposure sources |

## File Structure
```
d:\Exposed Cred\
├── chat_app.py              # Streamlit chat interface
├── app.py                   # Original daily report
├── requirements.txt         # Python dependencies
├── Backend/
│   ├── loader.py           # Excel file loader
│   ├── rules.py            # Analysis rules
│   └── predefined_tasks.py # Task definitions
├── Chains/
│   ├── intent_classifier.py    # Question classifier
│   └── response_formatter.py   # Response formatter
└── Data/
    └── format_cache.json   # Optional: LLM response cache
```

## Environment
- **LLM**: Ollama (local, no API key needed)
- **Model**: Mistral (default, changeable in Chains files)
- **Framework**: Streamlit (web interface)
- **Data**: Excel files (uploaded dynamically)

## Troubleshooting

**Error: "Connection refused" for Ollama**
- Make sure Ollama server is running: `ollama serve`
- Check it's on `http://localhost:11434`

**Error: "Files not loading"**
- Ensure Excel files have correct columns (Email, Date of Exposure, Source)
- Check file encoding (should be standard Excel format)

**Slow responses**
- Ollama processes locally; first query may take ~10 seconds
- Subsequent queries are faster

## Stopping the App
Press `Ctrl + C` in the terminal where Streamlit is running.

## Architecture Diagram

The following Mermaid diagram shows the high-level architecture and data flow for the application. If your Markdown renderer supports Mermaid, it will render automatically. To export as SVG/PNG, use a Mermaid CLI or online renderer.

```mermaid
flowchart LR
    subgraph UserLayer[User]
        U[User]
    end

    subgraph UILayer[Streamlit UI - `chat_app.py`]
        Upload[File Uploads\n(Current & Master Excel)]
        ChatIn[Chat Input]
        History[Chat History (session_state)]
        DownloadBtn[Download Excel Button]
    end

    subgraph AppLayer[Application Layer]
        Loader[Loader \n`Backend/loader.py`\n(loads Excel -> DataFrames)]
        Predef[Predefined Tasks\n`Backend/predefined_tasks.py`]
        IntentChain[Intent Classifier\n`Chains/intent_classifier.py`]
        Rules[Rules Engine\n`Backend/rules.py`\n(analysis & candidates)]
        FormatterChain[Response Formatter\n`Chains/response_formatter.py`]
        Cache[Format Cache\n`data/format_cache.json`]
        CLI[CLI Report `app.py`]
    end

    subgraph LLM[Local LLM]
        Ollama[Ollama Server\nhttp://localhost:11434\n(mistral)]
    end

    U --> UILayer
    Upload --> Loader
    Loader --> UILayer
    ChatIn --> Predef
    Predef -->|matched| Rules
    Predef -->|not matched| IntentChain
    IntentChain --> Rules
    Rules --> FormatterChain
    FormatterChain -->|cache lookup| Cache
    Cache -->|hit| FormatterChain
    FormatterChain -->|invoke| Ollama
    Ollama --> FormatterChain
    FormatterChain --> UILayer
    Rules --> DownloadBtn
    DownloadBtn --> U

    %% auxiliary flows
    CLI --> Loader
    CLI --> Rules
    CLI --> FormatterChain
    CLI --> Cache
    CLI --> Ollama

```

If you'd like, I can also add the generated `architecture.svg` and `architecture.png` files into the repository.
