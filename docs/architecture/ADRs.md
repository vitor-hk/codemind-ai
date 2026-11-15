# Architecture Decision Records (ADRs) — CodeMind AI

## ADR-01: Persistência Relacional/Vetorial Unificada no PostgreSQL + NetworkX em Memória
- **Contexto:** Necessidade de armazenar metadados relacionais, vetores de 768 dimensões e percorrer grafos de dependência complexos.
- **Decisão:** Utilizar **PostgreSQL 16 + `pgvector` + `pg_trgm`** como fonte única de verdade transacional (ACID) e construir os grafos direcionados sob demanda com **NetworkX**.
- **Consequência:** Elimina a sobrecarga de sincronizar múltiplos bancos heterogêneos (como Neo4j + Qdrant + Postgres) mantendo latência sub-10ms para análise de ciclos, acoplamento e caminhos transitivos.

## ADR-02: Análise Sintática Poliglota via Tree-sitter com Representação Intermediária (Unified Symbol IR)
- **Contexto:** Repositórios corporativos utilizam múltiplas linguagens (Python, TypeScript, JavaScript, Java).
- **Decisão:** Implementar o motor `TreeSitterAnalyzerEngine` convertendo a AST nativa de cada gramática para `ExtractedSymbolDTO` e classificando relações por nível explícito de certeza (`HIGH_AST`, `MEDIUM_SCOPED`, `LOW_HEURISTIC`).
- **Consequência:** Evita falsos positivos em linguagens dinâmicas e permite adicionar novas linguagens sem alterar o grafo ou o motor RAG.

## ADR-03: Chunking Semântico Orientado à AST + Busca Híbrida com Reciprocal Rank Fusion (RRF)
- **Contexto:** Divisão de código por tamanho fixo de caracteres quebra funções ao meio e perde o contexto da classe pai.
- **Decisão:** Desenvolver o `ASTSmartChunker` que respeita limites sintáticos de funções/classes, injeta cabeçalhos enriquecidos (`File`, `Signature`, `Calls`) e combina busca vetorial (`pgvector`) + busca lexical (`to_tsvector`) via **RRF** + Reranking de assinatura.
- **Consequência:** Alta precisão tanto para buscas conceituais em linguagem natural quanto para identificadores exatos de funções.

## ADR-04: Inferência Local Privada Desacoplada (Ollama Adapter) e Guardrails contra Prompt Injection
- **Contexto:** Código-fonte proprietário não deve ser enviado para APIs externas por padrão, e comentários de repositórios não confiáveis podem conter *prompt injections*.
- **Decisão:** Criar interfaces abstratas (`BaseLLMProvider` e `BaseEmbeddingProvider`) conectadas ao **Ollama** (`qwen2.5-coder:7b` e `nomic-embed-text`) e isolar todo código recuperado em tags `<untrusted_repository_code>`.
