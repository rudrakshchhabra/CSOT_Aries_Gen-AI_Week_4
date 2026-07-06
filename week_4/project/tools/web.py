import os
import json
import requests
import trafilatura

def web_search(query: str, num_results: int = 5) -> dict:
    url = "https://google.serper.dev/search"
    payload = {"q": query, "num": num_results}
    headers = {
        'X-API-KEY': os.environ.get("SERPER_API_KEY", ""),
        'Content-Type': 'application/json'
    }
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        results = []
        for item in data.get("organic", [])[:num_results]:
            results.append({
                "title": item.get("title", ""),
                "link": item.get("link", ""),
                "snippet": item.get("snippet", "")
            })
        return {"results": results}
    except Exception as e:
        return {"error": f"Search tool failed: {str(e)}"}

def web_fetch(url: str) -> dict:
    MAX_CHARS = 8000
    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return {"error": "Failed to fetch webpage content."}
        text = trafilatura.extract(downloaded, include_comments=False, include_tables=True)
        if not text:
            return {"error": "Failed to extract text from webpage."}
        
        content = text
        if len(content) > MAX_CHARS:
            content = content[:MAX_CHARS] + "\n\n[...truncated]"
            
        return {"content": content}
    except Exception as e:
        return {"error": f"Fetch tool failed: {str(e)}"}