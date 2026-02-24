# Sidecar Integration Guide

## Framework Examples

---

## LangChain

```python
from langchain.llms import OpenAI
from langchain.callbacks import BaseCallbackHandler
from swarm_it import SwarmIt, ValidationType

swarm = SwarmIt(url="http://localhost:8080")

class SwarmItCallback(BaseCallbackHandler):
    def __init__(self):
        self.current_cert = None

    def on_llm_start(self, serialized, prompts, **kwargs):
        # Certify before LLM call
        prompt = prompts[0] if prompts else ""
        self.current_cert = swarm.certify(prompt)

        if not self.current_cert.allowed:
            raise ValueError(f"Blocked: {self.current_cert.reason}")

    def on_llm_end(self, response, **kwargs):
        # Validate after LLM call
        if self.current_cert:
            swarm.validate(
                self.current_cert.id,
                ValidationType.TYPE_I,
                score=0.9,
                failed=False,
            )

# Usage
llm = OpenAI(callbacks=[SwarmItCallback()])
result = llm("What is the capital of France?")
```

---

## CrewAI

```python
from crewai import Agent, Task, Crew
from swarm_it import SwarmIt

swarm = SwarmIt(url="http://localhost:8080")

def certified_task(task_description: str):
    """Wrapper that certifies before task execution."""
    cert = swarm.certify(task_description)

    if not cert.allowed:
        return f"Task blocked: {cert.reason}"

    # Execute task...
    result = execute_task(task_description)

    # Validate
    swarm.validate(cert.id, "TYPE_I", score=0.9, failed=False)
    return result

# Usage with CrewAI
researcher = Agent(
    role="Researcher",
    goal="Research topics",
    backstory="Expert researcher",
)

task = Task(
    description="Research quantum computing",
    agent=researcher,
)

# Certify before crew runs
cert = swarm.certify(task.description)
if cert.allowed:
    crew = Crew(agents=[researcher], tasks=[task])
    result = crew.kickoff()
```

---

## AutoGen

```python
from autogen import AssistantAgent, UserProxyAgent
from swarm_it import SwarmIt

swarm = SwarmIt(url="http://localhost:8080")

class CertifiedAssistant(AssistantAgent):
    def generate_reply(self, messages, sender, config):
        # Get last message
        last_msg = messages[-1]["content"] if messages else ""

        # Certify
        cert = swarm.certify(last_msg)
        if not cert.allowed:
            return f"I cannot process this: {cert.reason}"

        # Generate reply
        reply = super().generate_reply(messages, sender, config)

        # Validate
        swarm.validate(cert.id, "TYPE_I", score=0.9, failed=False)
        return reply

# Usage
assistant = CertifiedAssistant(name="assistant", llm_config=llm_config)
user = UserProxyAgent(name="user")
user.initiate_chat(assistant, message="Hello!")
```

---

## FastAPI Middleware

```python
from fastapi import FastAPI, Request, HTTPException
from swarm_it import SwarmIt

app = FastAPI()
swarm = SwarmIt(url="http://localhost:8080")

@app.middleware("http")
async def certify_requests(request: Request, call_next):
    # Skip non-LLM endpoints
    if not request.url.path.startswith("/api/llm"):
        return await call_next(request)

    # Get prompt from body
    body = await request.json()
    prompt = body.get("prompt", "")

    # Certify
    cert = swarm.certify(prompt)
    if not cert.allowed:
        raise HTTPException(status_code=403, detail=cert.reason)

    # Store cert ID for validation
    request.state.cert_id = cert.id

    # Process request
    response = await call_next(request)

    # Validate on success
    if response.status_code == 200:
        swarm.validate(cert.id, "TYPE_I", score=0.9, failed=False)

    return response
```

---

## OpenAI Direct

```python
import openai
from swarm_it import SwarmIt

swarm = SwarmIt(url="http://localhost:8080")

def certified_completion(prompt: str, **kwargs):
    """OpenAI completion with RSCT certification."""
    # Pre-execution gate
    cert = swarm.certify(prompt)

    if not cert.allowed:
        return {"error": cert.reason, "certificate": cert}

    # Execute
    response = openai.ChatCompletion.create(
        model=kwargs.get("model", "gpt-4"),
        messages=[{"role": "user", "content": prompt}],
        **kwargs,
    )

    # Post-execution validation
    swarm.validate(cert.id, "TYPE_I", score=0.9, failed=False)

    return {
        "response": response,
        "certificate": cert,
    }

# Usage
result = certified_completion("Explain quantum entanglement")
```

---

## Anthropic Direct

```python
import anthropic
from swarm_it import SwarmIt

swarm = SwarmIt(url="http://localhost:8080")
client = anthropic.Anthropic()

def certified_message(prompt: str, **kwargs):
    """Anthropic message with RSCT certification."""
    cert = swarm.certify(prompt)

    if not cert.allowed:
        return {"error": cert.reason, "certificate": cert}

    response = client.messages.create(
        model=kwargs.get("model", "claude-3-opus-20240229"),
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    swarm.validate(cert.id, "TYPE_I", score=0.9, failed=False)

    return {
        "response": response,
        "certificate": cert,
    }
```

---

## Generic Pattern

```python
from swarm_it import SwarmIt, ValidationType

swarm = SwarmIt(url="http://localhost:8080")

def with_certification(llm_func):
    """Decorator to add RSCT certification to any LLM function."""
    def wrapper(prompt, *args, **kwargs):
        # Pre-execution
        cert = swarm.certify(prompt)

        if not cert.allowed:
            raise RuntimeError(f"Certification failed: {cert.reason}")

        # Execute
        try:
            result = llm_func(prompt, *args, **kwargs)
            failed = False
        except Exception as e:
            failed = True
            raise

        finally:
            # Post-execution
            swarm.validate(
                cert.id,
                ValidationType.TYPE_I,
                score=0.0 if failed else 0.9,
                failed=failed,
            )

        return result

    return wrapper

# Usage
@with_certification
def my_llm_call(prompt):
    return openai.ChatCompletion.create(...)
```

---

## Async Pattern

```python
from swarm_it import AsyncSwarmIt

async def certified_async(prompt: str):
    async with AsyncSwarmIt(url="http://localhost:8080") as swarm:
        cert = await swarm.certify(prompt)

        if not cert.allowed:
            return {"error": cert.reason}

        # Your async LLM call
        result = await my_async_llm(prompt)

        await swarm.validate(cert.id, "TYPE_I", score=0.9, failed=False)

        return result
```
