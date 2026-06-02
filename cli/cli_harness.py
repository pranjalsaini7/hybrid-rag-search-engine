#!/usr/bin/env python3
"""
CLI Test Harness — Interactive Terminal Interface

A quick way to test the RAG pipeline without a web UI.
Supports document upload, listing, deletion, and Q&A.

Usage:
    cd backend
    python -m cli.cli_harness

Commands:
    /upload <path>    Upload a PDF, DOCX, or TXT file
    /docs             List all uploaded documents
    /delete <id>      Delete a document by ID
    /clear            Clear the screen
    /health           Check server health
    /help             Show this help
    /quit             Exit
"""

from __future__ import annotations

import asyncio
import sys
import os
import httpx

# Default server URL
BASE_URL = os.getenv("RAG_SERVER_URL", "http://localhost:8000")


def print_banner():
    """Print a nice startup banner."""
    print()
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║       📚  Research Paper RAG Assistant  (CLI Mode)         ║")
    print("║                                                            ║")
    print("║   Hybrid Search  •  Cross-Encoder Reranking  •  LLaMA 3   ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()
    print("  Type a question to query your papers, or use a / command.")
    print("  Type /help for available commands.")
    print()


def print_help():
    print("""
  ╭─────────────────────────────────────────────╮
  │  /upload <path>   Upload a document         │
  │  /docs            List uploaded documents   │
  │  /delete <id>     Delete a document         │
  │  /clear           Clear screen              │
  │  /health          Server health check       │
  │  /help            Show this help            │
  │  /quit            Exit                      │
  ╰─────────────────────────────────────────────╯
""")


async def upload_file(client: httpx.AsyncClient, file_path: str):
    """Upload a file to the server."""
    import os
    from pathlib import Path

    path = Path(file_path.strip().strip('"').strip("'"))
    if not path.exists():
        print(f"  ❌ File not found: {path}")
        return

    print(f"  📤 Uploading '{path.name}' …")

    with open(path, "rb") as f:
        response = await client.post(
            f"{BASE_URL}/api/documents/upload",
            files={"file": (path.name, f, "application/octet-stream")},
            timeout=120.0,  # Summarization can take a while
        )

    if response.status_code == 200:
        data = response.json()
        print(f"  ✅ Uploaded successfully!")
        print(f"     ID:     {data['id']}")
        print(f"     Chunks: {data['chunk_count']}")
        print(f"     Type:   {data['file_type']}")
        if data.get("summary"):
            print(f"     Summary:")
            for line in data["summary"].split("\n"):
                print(f"       {line}")
    else:
        print(f"  ❌ Upload failed: {response.status_code} — {response.text}")


async def list_documents(client: httpx.AsyncClient):
    """List all uploaded documents."""
    response = await client.get(f"{BASE_URL}/api/documents/", timeout=10.0)

    if response.status_code != 200:
        print(f"  ❌ Error: {response.status_code}")
        return

    data = response.json()
    docs = data["documents"]

    if not docs:
        print("  📭 No documents uploaded yet.")
        return

    print(f"\n  📄 {data['total']} document(s):\n")
    print(f"  {'ID':<38} {'Filename':<30} {'Chunks':>6}  {'Type':<5}")
    print(f"  {'─'*38} {'─'*30} {'─'*6}  {'─'*5}")

    for doc in docs:
        print(
            f"  {doc['id']:<38} {doc['filename']:<30} "
            f"{doc['chunk_count']:>6}  {doc['file_type']:<5}"
        )
        if doc.get("summary"):
            # Show first line of summary
            first_line = doc["summary"].split("\n")[0][:60]
            print(f"  {'':38} 💡 {first_line}…")
    print()


async def delete_document(client: httpx.AsyncClient, doc_id: str):
    """Delete a document by ID."""
    doc_id = doc_id.strip()
    response = await client.delete(
        f"{BASE_URL}/api/documents/{doc_id}", timeout=10.0
    )

    if response.status_code == 200:
        print(f"  🗑️  Deleted document {doc_id}")
    elif response.status_code == 404:
        print(f"  ❌ Document not found: {doc_id}")
    else:
        print(f"  ❌ Error: {response.status_code} — {response.text}")


async def check_health(client: httpx.AsyncClient):
    """Check server health."""
    try:
        response = await client.get(f"{BASE_URL}/health", timeout=5.0)
        data = response.json()
        print(f"  🟢 Server is healthy")
        print(f"     Model:     {data.get('model', 'unknown')}")
        print(f"     Documents: {data.get('documents', 0)} chunks indexed")
    except Exception as e:
        print(f"  🔴 Server unreachable: {e}")


async def ask_question(client: httpx.AsyncClient, question: str):
    """Send a question and display the answer."""
    print(f"\n  🔍 Searching… (hybrid: {70}% vector + {30}% BM25, reranked)\n")

    try:
        response = await client.post(
            f"{BASE_URL}/api/chat",
            json={"query": question, "session_id": "cli"},
            timeout=120.0,
        )

        if response.status_code != 200:
            print(f"  ❌ Error: {response.status_code} — {response.text}")
            return

        data = response.json()

        # Print answer
        print("  📝 Answer:")
        print("  " + "─" * 56)
        for line in data["answer"].split("\n"):
            print(f"  {line}")
        print("  " + "─" * 56)

        # Print sources
        sources = data.get("sources", [])
        if sources:
            print(f"\n  📄 Sources ({len(sources)}):")
            for i, src in enumerate(sources, 1):
                page = f"p.{src['page_number']}" if src.get("page_number") else ""
                score = f"score {src.get('relevance_score', 0):.2f}"
                print(f"    [{i}] {src['document_name']} ({page}, {score})")
                # Show excerpt
                excerpt = src["chunk_text"][:150].replace("\n", " ")
                print(f"        \"{excerpt}…\"")
        print()

    except httpx.ConnectError:
        print("  🔴 Cannot connect to server. Is it running?")
        print(f"     Expected at: {BASE_URL}")
        print("     Start with:  uvicorn app.main:app --reload")
    except Exception as e:
        print(f"  ❌ Error: {e}")


async def main():
    """Main REPL loop."""
    print_banner()

    async with httpx.AsyncClient() as client:
        # Quick health check on startup
        await check_health(client)
        print()

        while True:
            try:
                user_input = input("  You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n  👋 Goodbye!")
                break

            if not user_input:
                continue

            # ── Commands ────────────────────────────────────────────
            if user_input.startswith("/"):
                parts = user_input.split(maxsplit=1)
                cmd = parts[0].lower()
                arg = parts[1] if len(parts) > 1 else ""

                if cmd == "/quit" or cmd == "/exit":
                    print("  👋 Goodbye!")
                    break
                elif cmd == "/help":
                    print_help()
                elif cmd == "/upload":
                    if not arg:
                        print("  Usage: /upload <file_path>")
                    else:
                        await upload_file(client, arg)
                elif cmd == "/docs":
                    await list_documents(client)
                elif cmd == "/delete":
                    if not arg:
                        print("  Usage: /delete <document_id>")
                    else:
                        await delete_document(client, arg)
                elif cmd == "/health":
                    await check_health(client)
                elif cmd == "/clear":
                    os.system("cls" if os.name == "nt" else "clear")
                    print_banner()
                else:
                    print(f"  Unknown command: {cmd}  (type /help)")
            else:
                # ── Question ────────────────────────────────────────
                await ask_question(client, user_input)


if __name__ == "__main__":
    asyncio.run(main())
