-- 0008 · Use exact vector search at demo corpus scale.
-- The ivfflat index (lists=100) was built for a large corpus, but with only a
-- few dozen document chunks the approximate search probes near-empty clusters
-- and returns too few (or zero) rows for unscoped queries. Exact cosine search
-- over a small corpus is sub-millisecond and always correct, so drop the index.
-- Re-introduce an ivfflat/hnsw index (with lists ≈ rows/1000 and higher
-- ivfflat.probes) only once the corpus grows into the thousands.
drop index if exists public.documents_embedding_idx;
