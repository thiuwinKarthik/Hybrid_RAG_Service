# Enterprise Hybrid RAG Intelligence Platform

A production-oriented, enterprise-grade Retrieval-Augmented Generation (RAG) system combining dense vector search (Qdrant HNSW), sparse keyword retrieval (BM25 Okapi), Reciprocal Rank Fusion (RRF), Cross-Encoder reranking, claim citation verification, composite confidence calculation, and developer explainability trace panels.

---

## System Architecture

```
React 18 Dashboard UI
         │
         ▼ HTTP REST
Node.js + Express API Gateway (JWT & RBAC Auth)
         │
    ┌────┴────────────────────────┬─────────────────────────┐
    ▼                             ▼                         ▼
PostgreSQL                      Redis                 Python FastAPI RAG Service
(Document Metadata)          (Query Cache)                  │
                                           ┌────────────────┴────────────────┐
                                           ▼                                 ▼
                                   Qdrant Vector DB                     BM25 Index
                                  (Dense ANN Cosine)                 (Sparse Lexical)
                                           │                                 │
                                           └────────────────┬────────────────┘
                                                            ▼
                                                Reciprocal Rank Fusion (RRF)
                                                            │
                                                            ▼
                                                 Cross-Encoder Reranker
                                                            │
                                                            ▼
                                                 Grounded LLM Generator
                                                            │
                                                            ▼
                                                  Citation Verification
                                                            │
                                                            ▼
                                                  Confidence Score Engine
```

---

## Features & Highlights

- **Multi-Format Document Ingestion**: Parse PDF, TXT, Markdown, and HTML documents into normalized text representations with page and section tracking.
- **Configurable Chunking Strategies**: Fixed-size window with overlap, Recursive structural splitter (headings/paragraphs), and Semantic similarity boundary detection.
- **Hybrid Retrieval & RRF**: Combines Qdrant dense vector cosine similarity with BM25 Okapi sparse keyword retrieval via Reciprocal Rank Fusion (`1 / (k + rank)`).
- **Cross-Encoder Reranking**: Re-scores top candidate chunks using `cross-encoder/ms-marco-MiniLM-L-6-v2` for precise relevance.
- **Citation & Fact Verification Engine**: Automatically parses claim citations (`[1]`, `[2]`), links back to source pages/sections, and verifies claims against source chunks (`SUPPORTED`, `PARTIALLY_SUPPORTED`, `UNSUPPORTED`).
- **Composite Confidence Calculation**: Weighted metric combining retrieval relevance, citation coverage, claim verification, and answer completeness. Triggers "I don't have enough information" when evidence is weak.
- **Developer Debug & Explainability Panel**: Step-by-step pipeline inspection displaying Dense scores, BM25 scores, RRF merged candidates, Reranker scores, System context, Claim verification, and Latency waterfall breakdown.
- **Golden Dataset Evaluation**: Automated benchmark measuring Retrieval Relevance, Faithfulness, Citation Accuracy, and Answer Correctness across test suites.

---

## Module Breakdown

| Module | Component | Description |
|---|---|---|
| **Module 1** | Foundation & Setup | Monorepo layout, Docker Compose, `.env` config templates |
| **Module 2** | User Auth & RBAC | JWT auth, password hashing, roles (ADMIN, EMPLOYEE) |
| **Module 3-4** | Document Management | Document lifecycle states (`UPLOADED` -> `COMPLETED`), async pipeline |
| **Module 5-7** | Ingestion & Embeddings | Parsing, 3 chunking strategies, SentenceTransformers vectorization |
| **Module 8-11** | Retrieval & Reranking | Qdrant HNSW ANN, BM25 Okapi, RRF rank merger, Cross-Encoder reranker |
| **Module 12-15**| RAG Generation & Trust | Grounded LLM, Citation mapping, Verification, Confidence engine |
| **Module 16-18**| Evaluation & Benchmark | Golden dataset test suite, comparative retrieval mode matrix |
| **Module 19-21**| Dashboard & Explainability| Modern React UI, Developer Debug panel, Admin analytics |
| **Module 22-27**| Production & Ops | Redis caching, Docker Compose multi-container setup, unit tests |

---

## Quick Start (Local & Docker)

### Option 1: Docker Compose (Recommended)
```bash
# Clone and navigate to repository
cd rag_project

# Launch all microservices (Postgres, Redis, Qdrant, FastAPI, Express Gateway, React Frontend)
docker-compose up --build
```
Access the React Dashboard at `http://localhost:3000`.

### Option 2: Local Microservices Execution

#### 1. FastAPI RAG Service
```bash
cd rag-service
pip install -r requirements.txt
python main.py
```
FastAPI runs on `http://localhost:8000`.

#### 2. Node.js API Gateway
```bash
cd gateway
npm install
npm start
```
Express Gateway runs on `http://localhost:4000`.

#### 3. React Frontend
```bash
cd frontend
npm install
npm run dev
```
React Dashboard runs on `http://localhost:3000`.

---

## Sample Documents & Testing

Use the pre-created sample documents in `sample_docs/`:
- `security_policy.md` (Password policy, account lockout, database access team)
- `employee_handbook.md` (Leave request procedure, remote work policy)
- `incident_playbook.txt` (Production database incident procedure, error `ERR_CONNECTION_RESET`)

### Sample Queries to Test
1. *"What is the password expiration policy?"* -> Returns 90 days with `[1]` citation from `security_policy.md`.
2. *"How do I request leave?"* -> Returns 5 business days via HR portal with citation from `employee_handbook.md`.
3. *"What is the procedure for a production database incident?"* -> Returns PagerDuty P1 procedure with citation from `incident_playbook.txt`.
4. *"What is the policy for quantum teleportation travel expenses?"* -> Triggers confidence threshold fallback: *"I don't have enough information in the available company documentation to answer this question."*

---

## Running Unit Tests & Benchmarks

```bash
# Run Python Pytest Unit Tests
cd rag-service
pytest tests/

# Run Automated Golden Dataset Evaluation
python evaluation/evaluator.py
```
