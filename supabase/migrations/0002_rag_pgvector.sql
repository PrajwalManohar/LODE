-- LODE Phase 1 · RAG vector store (replaces ChromaDB)
-- 384-dim embeddings from sentence-transformers all-MiniLM-L6-v2

create extension if not exists vector;

create table if not exists public.documents (
  id            text primary key,            -- chunk id (matches corpus chunk id)
  content       text not null,               -- the chunk text (the "exact details" for req #3)
  embedding     vector(384),
  source        text,                        -- e.g. "JEOL JSM-IT800 Manual"
  section       text,                        -- e.g. "Section 3.2"
  page          text,                        -- e.g. "42"
  corpus_type   text,                        -- manual | sop | run_log | maintenance
  instrument_id text,
  created_at    timestamptz not null default now()
);

-- Approximate-NN index (cosine). ivfflat needs data before it's useful; safe to create early.
create index if not exists documents_embedding_idx
  on public.documents using ivfflat (embedding vector_cosine_ops) with (lists = 100);
create index if not exists documents_instrument_idx on public.documents(instrument_id);
create index if not exists documents_corpus_type_idx on public.documents(corpus_type);

-- Similarity search RPC. Returns the chunk text + metadata + similarity so the
-- frontend can show the real source passage, not just a label (req #3).
create or replace function public.match_documents(
  query_embedding   vector(384),
  match_count       int default 5,
  filter_instrument text default null,
  filter_corpus     text default null
)
returns table (
  id            text,
  content       text,
  source        text,
  section       text,
  page          text,
  corpus_type   text,
  instrument_id text,
  similarity    float
)
language sql stable
as $$
  select
    d.id, d.content, d.source, d.section, d.page, d.corpus_type, d.instrument_id,
    1 - (d.embedding <=> query_embedding) as similarity
  from public.documents d
  where (filter_instrument is null or d.instrument_id = filter_instrument)
    and (filter_corpus is null or d.corpus_type = filter_corpus)
  order by d.embedding <=> query_embedding
  limit match_count;
$$;
