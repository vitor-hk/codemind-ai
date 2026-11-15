# 🧠 CodeMind AI
**Plataforma Inteligente de Análise Estática, Compreensão Arquitetural e Engenharia de Software com Graph-RAG Local**

![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-TypeScript-61DAFB?logo=react&logoColor=black)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL_16-pgvector-4169E1?logo=postgresql&logoColor=white)
![Tree-sitter](https://img.shields.io/badge/AST-Tree--sitter-10B981)
![Ollama](https://img.shields.io/badge/Local_AI-Ollama-F59E0B)

O **CodeMind AI** é uma plataforma de engenharia de software projetada para importar repositórios reais, extrair sua estrutura sintática via **Tree-sitter (AST)**, mapear dependências em grafos direcionados com **NetworkX**, indexar semanticamente o código no **PostgreSQL (`pgvector` + Full-Text Search)** e responder perguntas arquiteturais complexas ou simular o impacto de alterações utilizando **LLMs locais via Ollama** — garantindo **100% de privacidade para códigos corporativos**.

---

## ✨ Principais Capacidades de Engenharia

1. **Repository Manager & Security Scanner:**
   - Importação de repositórios Git (públicos ou privados) e arquivos `.zip` com proteção contra *Zip Slip / Path Traversal*.
   - Respeito nativo ao `.gitignore`, bloqueio de diretórios de dependências (`node_modules`, `.venv`, `dist`, `target`) e exclusão automática de segredos (`.env`, `.pem`, `.key`, `id_rsa`).
   - Cálculo de hash criptográfico **SHA-256** por arquivo e chunk para **indexação incremental** (evita reprocessar código inalterado).
2. **Code Analysis Engine (Tree-sitter Poliglota):**
   - Extração determinística de **Classes, Interfaces, Funções, Métodos, Construtores, Assinaturas, Docstrings, Heranças e Chamadas** para **Python, TypeScript, JavaScript e Java**.
   - Classificação explícita do nível de confiança de cada relacionamento: `HIGH_AST` (comprovado na árvore sintática), `MEDIUM_SCOPED` (resolvido via escopo de imports) e `LOW_HEURISTIC`.
3. **Dependency Graph Engine (NetworkX):**
   - Construção de grafos de arquivos e de chamadas de símbolos.
   - Detecção automática de **Dependências Circulares (Ciclos)**, cálculo de **Acoplamento Aferente (Fan-In)**, **Acoplamento Eferente (Fan-Out)**, **Instabilidade de Robert C. Martin**, **Centralidade** e **Pontos de Entrada**.
4. **Semantic Indexing & Hybrid Search (pgvector + FTS + RRF):**
   - **AST-Aware Smart Chunking:** Fatiamento guiado pelas fronteiras sintáticas de funções e métodos com enriquecimento de cabeçalho contextual.
   - **Busca Híbrida com Reciprocal Rank Fusion (RRF):** Combina busca vetorial densa (`nomic-embed-text` 768 dims no `pgvector`) com busca lexical (`PostgreSQL Full-Text Search`) e Reranker de assinatura de símbolos.
5. **Graph-RAG & Impact Analysis Engine:**
   - Classificação automática da intenção da pergunta (`ARCHITECTURE_OVERVIEW`, `IMPACT_ANALYSIS`, `EXECUTION_FLOW`, `IMPLEMENTATION_LOOKUP`).
   - **Citações Verificáveis Clicáveis:** Toda resposta referencia `caminho/arquivo.ext:L10-L25`, abrindo o **Monaco Editor** diretamente nas linhas citadas.
   - **Simulador de Raio de Impacto (Blast Radius):** Identifica dependentes diretos, propagação transitiva, testes automatizados relacionados e calcula o score de risco (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`).

---

## 🏗️ Arquitetura do Sistema

```text
+-----------------------------------------------------------------------------------+
|                FRONTEND (React + TypeScript + Tailwind + Vite)                    |
|  [Dashboard] [Repo Explorer] [React Flow Graph] [Monaco Code Viewer] [RAG Chat]   |
+-----------------------------------------+-----------------------------------------+
                                          | REST API (FastAPI + Pydantic v2)
                                          v
+-----------------------------------------------------------------------------------+
|                        CORE ENGINES (Clean Architecture)                          |
|  - RepositoryScanner (SHA-256 Incremental + ZipSlip/Secret Guardrails)            |
|  - TreeSitterAnalyzerEngine (Python, TS, JS, Java -> Unified Symbol IR)           |
|  - DependencyGraphEngine (NetworkX DiGraph, Cycles, Centrality, Instability)      |
|  - ASTSmartChunker + SemanticSearchService (pgvector Cosine + Postgres FTS + RRF) |
|  - GraphRAGEngine + ImpactAnalysisService + OllamaLLMProvider                     |
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|   [PostgreSQL 16 + pgvector + pg_trgm]     [Redis 7]     [Ollama Local Server]    |
+-----------------------------------------------------------------------------------+
```

Consulte as decisões arquiteturais detalhadas em [`docs/architecture/ADRs.md`](docs/architecture/ADRs.md) e os resultados de benchmark em [`docs/benchmarks/BENCHMARK_RESULTS.md`](docs/benchmarks/BENCHMARK_RESULTS.md).

---

## 🚀 Como Executar Localmente (macOS / Linux)

### 1. Pré-requisitos
- **Docker** e **Docker Compose**
- **Python 3.12+** e **Node.js 20+**
- **Ollama** rodando localmente com os modelos `nomic-embed-text` e `qwen2.5-coder:7b`

### 2. Subir Banco Vetorial e Redis
```bash
cp .env.example .env
docker compose up -d
```

### 3. Executar Backend e Testes Automatizados
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install --prefer-binary -r requirements.txt
PYTHONPATH=. pytest -v
uvicorn app.main:app --reload --port 8000
```

### 4. Executar Frontend
```bash
cd frontend
npm install --legacy-peer-deps
npm run dev
```

---

## 🧪 Qualidade, Segurança e Métricas de RAG

O projeto inclui avaliação automatizada de recuperação de informação (`app/rag/evaluator.py`) calculando **Precision@K**, **Recall@K**, **MRR (Mean Reciprocal Rank)**, **NDCG@K** e **Latência de Recuperação Híbrida (ms)**.

---
Desenvolvido por **Vitor Hugo Koehler** como projeto de Engenharia de Software & Inteligência Artificial Aplicada.
