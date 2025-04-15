#!/usr/bin/env python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import datetime
import warnings
import os
import subprocess
import yaml
import json
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task

warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")


app = FastAPI(title="Crew AI Bot API", description="API to run Crew AI Bot", version="1.0.0")


class AgentRunInput(BaseModel):
    topic: str
    author_name: str
    author_picture_url: str = ""
    cover_image_url: str = ""


@CrewBase
class CrewAiBot:
    """CrewAiBot crew"""
    agents_config = 'config/agents.yaml'
    tasks_config = 'config/tasks.yaml'

    @agent
    def researcher(self) -> Agent:
        return Agent(
            config=self.agents_config['researcher'],
            verbose=True
        )

    @agent
    def writer(self) -> Agent:
        return Agent(
            config=self.agents_config['writer'],
            verbose=True
        )

    @agent
    def git_manager(self) -> Agent:
        return Agent(
            config=self.agents_config['git_manager'],
            verbose=True
        )

    @task
    def research_task(self) -> Task:
        return Task(
            config=self.tasks_config['research_task'],
        )

    @task
    def write_blog_post_task(self) -> Task:
        return Task(
            config=self.tasks_config['write_blog_post_task'],
            output_file='report.md'
        )

    @task
    def git_push_task(self) -> Task:
        repo_path = "/home/mibaloch/Desktop/ai/portfolio/outstatic/content/blogs"
        metadata_file_path = "/home/mibaloch/Desktop/ai/portfolio/outstatic/content"
        pat = os.getenv("GIT_TOKEN")

        def process_file(file_path):
            with open(file_path, 'r') as f:
                content = f.read()

            cleaned_content = content.strip()
            if cleaned_content.startswith('```markdown') or cleaned_content.startswith('```'):
                start_idx = cleaned_content.index('\n') + 1 if '\n' in cleaned_content else len(cleaned_content)
                end_idx = cleaned_content.rfind('```') if '```' in cleaned_content else len(cleaned_content)
                cleaned_content = cleaned_content[start_idx:end_idx].strip()

            metadata = {}
            if cleaned_content.startswith('---'):
                frontmatter_end = cleaned_content.index('---', 3)
                frontmatter = cleaned_content[3:frontmatter_end].strip()
                metadata = yaml.safe_load(frontmatter)
                slug = metadata.get('slug', 'default-slug')
            else:
                slug = 'default-slug'

            with open(file_path, 'w') as f:
                f.write(cleaned_content)

            return slug, metadata

        def update_metadata_json(repo_path, metadata):
            metadata_file = os.path.join(repo_path, 'metadata.json')
            if os.path.exists(metadata_file):
                with open(metadata_file, 'r') as f:
                    metadata_json = json.load(f)
            else:
                metadata_json = {"metadata": []}

            new_entry = {
                "category": metadata.get('category', 'Uncategorized'),
                "collection": "blogs",
                "coverImage": metadata.get('coverImage', ''),
                "description": metadata.get('description', ''),
                "publishedAt": metadata.get('publishedAt', ''),
                "slug": metadata.get('slug', 'default-slug'),
                "status": metadata.get('status', 'draft'),
                "title": metadata.get('title', 'Untitled'),
                "path": f"outstatic/content/blogs/{metadata.get('slug', 'default-slug')}.md",
                "author": {
                    "name": metadata.get('author', {}).get('name', ''),
                    "picture": metadata.get('author', {}).get('picture', '')
                },
                "__outstatic": {
                    "path": f"outstatic/content/blogs/{metadata.get('slug', 'default-slug')}.md",
                }
            }
            metadata_json['metadata'].append(new_entry)

            with open(metadata_file, 'w') as f:
                json.dump(metadata_json, f, indent=2)

        def push_to_git(task_output):
            original_file = 'report.md'
            slug, metadata = process_file(original_file)
            new_filename = f"{slug}.md"
            new_file_path = os.path.join(repo_path, new_filename)

            update_metadata_json(metadata_file_path, metadata)

            subprocess.run([
                "bash", "-c",
                f"mv {original_file} {new_file_path} && "
                f"git -C {repo_path} add {new_filename} && "
                f"git -C {repo_path} commit -m 'Add {new_filename} to outstatic/content/blogs' && "
                f"git -C {repo_path} push https://{pat}@github.com/abdullahhsajid/bmd-portfolio.git main"
            ], cwd=os.getcwd(), check=True)

        return Task(
            config=self.tasks_config['git_push_task'],
            callback=push_to_git
        )

    @crew
    def crew(self) -> Crew:
        """Creates the CrewAiBot crew"""
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )


@app.get("/")
async def root():
    return {"message": "Crew AI Bot API is running"}


@app.post("/run-agent")
async def run_agent(inputs: AgentRunInput):
    try:
        current_datetime_iso = datetime.now().isoformat() + "Z"
        crew_inputs = {
            "topic": inputs.topic,
            "current_year": str(datetime.now().year),
            "current_date_iso": current_datetime_iso,
            "author_name": inputs.author_name,
            "author_picture_url": inputs.author_picture_url,
            "cover_image_url": inputs.cover_image_url,
        }

        result = CrewAiBot().crew().kickoff(inputs=crew_inputs)

        return {
            "status": "success",
            "message": "Agent executed successfully",
            "result": str(result)  # Adjust based on actual output
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred while running the agent: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)