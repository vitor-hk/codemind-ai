# CodeMind AI — Benchmark de Qualidade de Recuperação Híbrida (Graph-RAG)

- **Top-K avaliado:** K=3
- **Total de Consultas Técnicas (Polyglot: Python, TypeScript, Java):** 3
- **Mean Recall@3:** `100.00%`
- **Mean Precision@3:** `33.33%`
- **MRR (Mean Reciprocal Rank):** `1.0000`
- **Mean NDCG@3:** `1.0000`
- **Latência Média de Recuperação Híbrida:** `185.44 ms`

| Consulta Técnica | Arquivos Recuperados (Top-K) | Recall@3 | RR | NDCG@3 | Latência (ms) |
| :--- | :--- | :---: | :---: | :---: | :---: |
| authenticate user JWT password login | `app/auth_service.py`, `app/auth_service.py`, `app/InventoryManager.java` | 1.00 | 1.00 | 1.00 | 471.87 |
| calculate order total subtotal discount | `app/payment_processor.ts`, `app/payment_processor.ts`, `app/InventoryManager.java` | 1.00 | 1.00 | 1.00 | 44.88 |
| reserve stock item inventory sku quantity | `app/InventoryManager.java`, `app/InventoryManager.java`, `app/payment_processor.ts` | 1.00 | 1.00 | 1.00 | 39.57 |
