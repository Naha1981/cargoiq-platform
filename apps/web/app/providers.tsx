"use client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "react-hot-toast";
import { useState } from "react";

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => new QueryClient({
    defaultOptions: {
      queries: { staleTime: 30_000, retry: 1 },
    },
  }));

  return (
    <QueryClientProvider client={queryClient}>
      {children}
      <Toaster
        position="top-right"
        toastOptions={{
          duration: 4000,
          style: {
            background: "#FFFFFF",
            color: "#0D1B2A",
            border: "1px solid #C8D0DA",
            borderRadius: "4px",
            fontSize: "13px",
            boxShadow: "0 4px 20px rgba(13,27,42,0.12)",
          },
        }}
      />
    </QueryClientProvider>
  );
}
