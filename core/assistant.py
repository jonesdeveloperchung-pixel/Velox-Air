# core/assistant.py

import os
import psutil
import aiohttp
import asyncio
from .knowledge_base import KnowledgeBase
from .debug import Debug

class AssistantManager:
    def __init__(self, debug: Debug = Debug()):
        self.debug = debug
        self.kb = KnowledgeBase()
        self.ollama_url = "http://127.0.0.1:11434/api/generate"
        self.ram_gb = psutil.virtual_memory().total / (1024**3)
        self.level = self._determine_initial_level()

    def _determine_initial_level(self):
        if self.ram_gb < 8:
            self.debug.info("Assistant", f"Low RAM detected ({self.ram_gb:.1f}GB). Defaulting to Standard Mode.")
            return "Standard"
        return "Checking" # Will check for Ollama presence later

    async def get_advice(self, issue: str):
        """Orchestrates the fallback logic to provide advice."""
        
        # Level 1: Try Local LLM (Ollama)
        if self.level != "Standard":
            try:
                async with aiohttp.ClientSession() as session:
                    prompt = f"你是一位專業的系統工程師助手。使用者遇到以下問題：'{issue}'。請使用簡短、友善的繁體中文提供解決步驟。"
                    payload = {
                        "model": "gemma2:2b", # Safe default
                        "prompt": prompt,
                        "stream": False
                    }
                    async with session.post(self.ollama_url, json=payload, timeout=5) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            return {
                                "level": "Smart (Ollama)",
                                "title": "AI 助手建議",
                                "content": data.get("response", "")
                            }
            except Exception:
                self.debug.debug("Assistant", "Ollama not reachable, falling back to Knowledge Base.")

        # Level 3: Fallback to Offline Knowledge Base
        return self.kb.query(issue)

    def get_status(self):
        return {
            "level": self.level,
            "ram_gb": round(self.ram_gb, 1),
            "kb_rules_count": len(self.kb.rules)
        }
