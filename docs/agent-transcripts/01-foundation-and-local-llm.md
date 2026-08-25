# 01 — Foundation and Local LLM

This record documents the initial foundation of the Lenny Growth Assistant: the backend API, PostgreSQL persistence, local model environment, embeddings, and provider execution setup.

## 1. Initial Environment Verification

Before building the application, the local development environment was verified to make sure the required infrastructure could run on the target machine.

The environment included:

- Python 3.12
- Node.js
- Docker and Docker Compose
- PostgreSQL tooling
- Ollama
- Pi Coding Agent

Ollama already had `llama3.2:3b` available locally.

A direct Ollama chat request was tested before integrating it into the application. The model successfully returned:

`OLLAMA_WORKS`

Pi Coding Agent was then tested against the same local Ollama installation using:

`pi --provider ollama --model "llama3.2:3b" --no-tools --no-session`

The successful response was:

`PI_OLLAMA_WORKS`

These checks separated infrastructure problems from application-level problems before the backend integration began.

## 2. Backend and Database Foundation

The backend was implemented with FastAPI.

PostgreSQL was selected for both application persistence and knowledge storage. The database stores application state such as sessions and messages, while the `pgvector` extension supports vector embeddings for the retrieval system.

SQLAlchemy's asynchronous engine and session management were used for database access.

The knowledge schema includes document-level metadata and chunk-level content. Knowledge chunks store 768-dimensional vector embeddings alongside their source metadata so retrieved evidence can be traced back to the original document.

During local setup, an existing PostgreSQL installation was detected on the host machine. To avoid conflicting with the host database, the Dockerized pgvector PostgreSQL service was configured on a separate host port.

The database setup was verified before moving on to ingestion and retrieval.

## 3. Local Embeddings

Knowledge ingestion and retrieval use `nomic-embed-text` embeddings through Ollama.

Before building the ingestion pipeline around the model, the Ollama embedding endpoint was tested directly.

The test returned a 768-dimensional vector, confirming that the embedding model and the database vector dimension agreed.

This was important because a mismatch between the model output dimension and the `pgvector` column would otherwise cause ingestion or retrieval failures later.

## 4. Local Generation

The mandatory demo path uses Ollama so the application can run without requiring a paid cloud model.

The initial local model used for conversational generation was:

`llama3.2:3b`

A second local model, `qwen3:4b-instruct`, was later used for more demanding structured generation such as artifacts and Ship 30 output.

Provider execution was kept behind the assistant/provider layer rather than being embedded directly inside API routes. This allowed the API and product workflows to remain independent of the selected model.

## 5. Pi Coding Agent Integration

The assignment required the agent layer to use an accepted agent framework. Pi Coding Agent was selected for this role.

The backend integrates with Pi through a `PiAgentClient`.

Instead of coupling the application directly to a cloud-provider Python SDK, the client invokes the Pi CLI asynchronously and parses its output.

This provided a common execution boundary while allowing the configured provider and model to change without rewriting the product workflows.

A model configuration file is included in the backend Docker setup so Pi can resolve the models available to the application.

## 6. Docker and Reproducible Startup

Docker Compose was used to make the system reproducible for another engineer or evaluator.

The application is separated into services for:

- PostgreSQL with pgvector
- FastAPI backend
- React/Vite frontend

The backend container contains the Python application dependencies and the Pi Coding Agent runtime required by the agent layer.

Ollama runs on the host machine and is reachable from the container through the configured Ollama base URL.

The knowledge ingestion workflow can also run against the same database and embedding configuration.

## 7. Health Verification

After the backend foundation was assembled, the health endpoint was tested:

`GET /health`

The backend returned a successful response identifying the Lenny Growth Assistant service and development environment.

This provided a minimal operational check before adding retrieval, grounding, provider routing, and artifact generation.

## 8. Problems Encountered and Corrections

### Existing PostgreSQL instance

A PostgreSQL instance was already running on the development machine.

Rather than replacing or stopping the host database, the Dockerized pgvector database was configured to use a different host port.

This kept the project environment isolated from the existing installation.

### Verifying the agent stack before application integration

Pi and Ollama were tested independently before wiring them into FastAPI.

This avoided debugging the application, Pi, Ollama, and model configuration simultaneously.

The successful `OLLAMA_WORKS` and `PI_OLLAMA_WORKS` checks confirmed that local inference worked before application code depended on it.

### Embedding dimension verification

The embedding model was tested before bulk ingestion.

`nomic-embed-text` returned the expected 768-dimensional vector, which was then matched by the PostgreSQL vector column.

This prevented a schema/model incompatibility from surfacing only after the transcript corpus had been processed.

## 9. Result

At the end of this phase, the project had:

- a working FastAPI backend,
- PostgreSQL + pgvector persistence,
- verified local Ollama inference,
- verified Pi Coding Agent execution,
- local `nomic-embed-text` embeddings,
- Docker-based service orchestration,
- and a working health endpoint.

This foundation was then used to build the transcript ingestion, hybrid retrieval, conversational grounding, provider routing, and artifact workflows documented in the following records.
