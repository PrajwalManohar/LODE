import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";

export default function StatusBanner() {
  const { data, isError } = useQuery({
    queryKey: ["status"],
    queryFn: api.status,
    retry: 2,
    refetchInterval: 60_000,
  });

  if (isError) {
    return (
      <span className="chip bg-danger-50 text-danger-700">
        API offline — uvicorn not running
      </span>
    );
  }
  if (!data) return null;

  return (
    <span className="chip bg-ok-50 text-ok-700">
      <span className="w-1.5 h-1.5 rounded-full bg-ok-600" />
      RAG corpus · {data.rag_chunks}
    </span>
  );
}
