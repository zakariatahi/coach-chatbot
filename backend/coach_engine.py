"""Builds the LangChain agent executor — reuses Coach.py tools as-is."""

import os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from langchain_ollama import ChatOllama
from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from Coach import UserProfile, make_profile_tools, tools_list, build_prompt

MODEL = os.getenv("OLLAMA_MODEL", "gemma4:e2b")


def build_executor(log_content: str, profile: UserProfile) -> AgentExecutor:
    """Build a streaming-capable agent executor for a given user + log."""
    llm = ChatOllama(
        model=MODEL,
        streaming=True,
        num_ctx=32768,
        num_thread=max(1, os.cpu_count() - 1),
    )
    all_tools = tools_list + make_profile_tools(profile)
    prompt    = build_prompt(log_content)
    agent     = create_tool_calling_agent(llm, all_tools, prompt)
    return AgentExecutor(agent=agent, tools=all_tools, verbose=False, max_iterations=6)
