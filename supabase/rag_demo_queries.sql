-- ============================================================================
-- LODE · RAG demo queries (paste into the Supabase SQL editor)
-- Shows what the knowledge base is indexed on and how cosine retrieval works.
-- pgvector operator <=> = cosine DISTANCE; cosine SIMILARITY = 1 - distance.
-- Embeddings: all-MiniLM-L6-v2, 384-dim, stored in public.documents.embedding.
-- ============================================================================

-- 1) Corpus inventory — chunk counts by type --------------------------------
select corpus_type, count(*) as chunks
from documents
group by corpus_type
order by chunks desc;

-- 2) Source documents — "what it's trained (retrieved) against" -------------
select source, corpus_type, max(instrument_id) as instrument, count(*) as chunks
from documents
group by source, corpus_type
order by corpus_type, source;

-- 3) Prove the vectors are real 384-dim embeddings --------------------------
select id, source, vector_dims(embedding) as dims,
       left(embedding::text, 60) || ' …]' as embedding_preview
from documents
limit 5;

-- 4) Cosine-similarity retrieval (PURE SQL — no embedding service needed) ----
--    Use one chunk as the "query" and rank every chunk by closeness to it.
--    Swap the id to demo a different topic (see ids from query #2 / browse).
with q as (
  select embedding from documents where id = 'sem-manual-3.2'  -- SEM fracture-imaging chunk
)
select d.source, d.section, d.corpus_type, d.instrument_id,
       round((1 - (d.embedding <=> q.embedding))::numeric, 4) as cosine_similarity
from documents d, q
order by d.embedding <=> q.embedding
limit 6;

-- 5) The ACTUAL function the app calls (match_documents), with an existing
--    chunk's embedding as the query vector. Args: (vector, top_k, instrument, corpus)
select source, section, corpus_type, instrument_id,
       round(similarity::numeric, 4) as cosine_similarity
from match_documents(
       (select embedding from documents where id = 'icp-manual-2.4'),
       5, null, null);

-- 6) Instrument-scoped retrieval (keeps XRD answers on XRD docs) -------------
select source, section, round(similarity::numeric, 4) as sim
from match_documents(
       (select embedding from documents where id = 'xrd-manual-4.3'),
       5, 'xrd-d8', null);

-- 7) Filter by corpus_type (e.g. only safety regulations) -------------------
select source, section, round(similarity::numeric, 4) as sim
from match_documents(
       (select embedding from documents where id = 'ehs-hazmat'),
       5, null, 'regulation');

-- Handy: list chunk ids to pick a "query" chunk for #4–#7
-- select id, source, section from documents order by corpus_type, source;
