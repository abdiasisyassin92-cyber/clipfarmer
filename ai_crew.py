import os
import sys
from crewai import Agent, Task, Crew, Process, LLM
from crewai_tools import FileReadTool, FileWriterTool

# 🔑 EXPLICIT GEMINI ENGINE INITIALIZATION
model_brain = LLM(
    model="gemini-2.5-flash",
    api_key="AQ.Ab8RN6KTKEFnWFysteGACM_5a08VLS0JKn_tI_JZk3PqI936jA"
)

# Initialize file manipulation tools
file_reader = FileReadTool(description="Allows agents to read state from C:\\clipfarmer\\config.json.")
file_writer = FileWriterTool(description="Allows the Code Architect to write scripts to C:\\clipfarmer\\.")

# Define the Worker Agent Array with Gemini Branded Routing
echo_agent = Agent(
    role="Lead Systems Engineer",
    goal="Orchestrate data integration topologies and ensure config stability.",
    backstory="You are Echo, managing the configuration file array and parsing log errors.",
    tools=[file_reader],
    llm=model_brain,
    allow_delegation=True,
    verbose=True
)

claude_agent = Agent(
    role="Lead Code Architect",
    goal="Write complete, high-performance Python modules autonomously.",
    backstory="You are Claude, writing production-ready automation scripts like tiktok_uploader.py.",
    tools=[file_reader, file_writer],
    llm=model_brain,
    allow_delegation=False,
    verbose=True
)

google_agent = Agent(
    role="Real-Time Research Analyst & Compliance Auditor",
    goal="Audit live API developer documentation schemas.",
    backstory="You are Google AI, verifying endpoint shifts and token constraints.",
    tools=[],
    llm=model_brain,
    allow_delegation=False,
    verbose=True
)

# Define the Task Pipeline
monitor_environment_task = Task(
    description="Inspect the contents of C:\\clipfarmer\\config.json.",
    expected_output="A structural integration report outlining local path states.",
    agent=echo_agent
)

audit_compliance_task = Task(
    description="Audit the TikTok sandbox endpoint documentation constraints.",
    expected_output="A clean metadata parameter validation map detailing token structures.",
    agent=google_agent
)

generate_tiktok_pipeline_task = Task(
    description="Implement the complete, production-ready script C:\\clipfarmer\\tiktok_uploader.py.",
    expected_output="Full python code module written directly to C:\\clipfarmer\\tiktok_uploader.py.",
    agent=claude_agent
)

# Assemble the Autonomous Crew
clipfarmer_crew = Crew(
    agents=[echo_agent, claude_agent, google_agent],
    tasks=[monitor_environment_task, audit_compliance_task, generate_tiktok_pipeline_task],
    process=Process.sequential,
    memory=False,
    verbose=True
)

if __name__ == "__main__":
    print("[SYSTEM INFO] Initializing Autonomous ClipFarmer Agent Crew via Gemini...")
    print("[SYSTEM INFO] Operator Registered: Kenister")
    
    # Trigger execution sequence
    result = clipfarmer_crew.kickoff()