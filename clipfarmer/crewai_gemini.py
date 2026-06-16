# ClipFarmer — CrewAI + Gemini 2.5 Flash Pipeline
#
# BEFORE RUNNING:
#   pip install crewai crewai-tools
#
# SET ENVIRONMENT VARIABLES (Windows CMD):
#   set GEMINI_API_KEY=your_gemini_key_here
#   set SERPER_API_KEY=your_serper_key_here
#
# RUN:
#   python crewai_gemini.py
#
# OUTPUT: blog_post.md will be written to the same folder.

import os
import sys
from crewai import Agent, Crew, Process, Task
from crewai_tools import SerperDevTool

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
SERPER_API_KEY = os.environ.get("SERPER_API_KEY")

if not GEMINI_API_KEY:
    print("[FATAL] GEMINI_API_KEY is not set.")
    sys.exit(1)

if not SERPER_API_KEY:
    print("[FATAL] SERPER_API_KEY is not set.")
    sys.exit(1)

search_tool = SerperDevTool()

researcher = Agent(
    role="Senior Research Analyst",
    goal="Find and summarize the top 5 developments in AI content automation for 2026.",
    backstory=(
        "You are a meticulous analyst who specializes in emerging technology trends. "
        "You surface accurate, data-backed insights and present them in structured form."
    ),
    llm="gemini/gemini-1.5-flash",
    tools=[search_tool],
    verbose=True,
    allow_delegation=False,
)

writer = Agent(
    role="Content Strategist and Writer",
    goal="Turn research findings into a compelling B2B blog post.",
    backstory=(
        "You are an expert content strategist who converts dense research into "
        "clear, persuasive narratives for professional audiences."
    ),
    llm="gemini/gemini-2.5-flash",
    verbose=True,
    allow_delegation=False,
)

research_task = Task(
    description=(
        "Research the 2026 AI content automation landscape. "
        "Identify the top 5 developments, tools, or trends with concrete examples or data points. "
        "Structure your output as a numbered list with 2-3 sentences per finding."
    ),
    expected_output=(
        "A numbered list of 5 findings about AI content automation in 2026. "
        "Each finding must be 2-3 sentences and include at least one specific example or statistic."
    ),
    agent=researcher,
)

writing_task = Task(
    description=(
        "Using the research findings, write a 400-word professional blog post for a B2B SaaS audience. "
        "Open with a strong hook. Use 3-4 paragraphs. End with a clear call to action."
    ),
    expected_output=(
        "A 400-word blog post in markdown format with a title, "
        "3-4 body paragraphs, and a closing call to action."
    ),
    agent=writer,
    context=[research_task],
    output_file="blog_post.md",
)

crew = Crew(
    agents=[researcher, writer],
    tasks=[research_task, writing_task],
    process=Process.sequential,
    memory=False,
    verbose=True,
)

if __name__ == "__main__":
    print("\n[ClipFarmer] Pipeline starting...\n")
    try:
        result = crew.kickoff()
        print("\n" + "=" * 60)
        print("PIPELINE COMPLETE — output saved to blog_post.md")
        print("=" * 60)
        print(result)
    except Exception as e:
        print(f"\n[ERROR] {type(e).__name__}: {e}")
        sys.exit(1)