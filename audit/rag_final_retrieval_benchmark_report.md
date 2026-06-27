# RAG Final Retrieval Benchmark Report

## Kapsam
`MIN_RETRIEVAL_SCORE=0.50` karar? kal?c? default config de?erine i?lendi ve kullan?c? taraf?ndan verilen son retrieval benchmark sonucu raporland?. Benchmark tekrar ?al??t?r?lmad?.

## Config Kayna??
- Ayar kayna??: `backend/app/config.py`
- Alan: `Settings.min_retrieval_score`
- Yeni default de?er: `0.50`
- `.env.local`: dokunulmad?

## Son Benchmark Sonucu
- case_count: `183`
- top_1: `0.7978`
- top_3: `1.0`
- mrr: `0.8971`
- failures: `[]`

## Parse Do?rulama
- `backend/app/config.py` AST parse: `PASS`
- `min_retrieval_score` default do?rulamas?: `PASS` (`0.5`)
- `backend\tests\fixtures\retrieval_benchmark.json` parse: `PASS`
- `output\rag_benchmark\rag_retrieval_benchmark_labels.json` parse: `PASS`
- `output\rag_benchmark\failure_score_probe.json` parse: `PASS`
- `output\rag_benchmark\threshold_dry_run_results.json` parse: `PASS`
- `output\rag_benchmark\rag_retrieval_benchmark_questions.jsonl` parse: `PASS (183 rows)`
- `output\rag_benchmark\rag_retrieval_benchmark_adapter.jsonl` parse: `PASS (183 rows)`

## Riskler
- Runtime ortam?nda `.env.local` veya process env `MIN_RETRIEVAL_SCORE` de?eri verirse Pydantic settings default de?erini override edebilir. Bu a?amada gizli env dosyas?na dokunulmad?.
- DB/ingest ve benchmark bu a?amada ?zellikle ?al??t?r?lmad?; raporlanan skor kullan?c? taraf?ndan sa?lanan son benchmark sonucudur.

## Genel Karar
PASS

## Sonraki ?nerilen Ad?m
Bu default de?erle deployment/staging ortam env de?erlerinin ?ak??mad??? kontrol edilmeli; gerekirse yaln?zca env y?netimi seviyesinde `MIN_RETRIEVAL_SCORE=0.50` teyit edilmelidir.
