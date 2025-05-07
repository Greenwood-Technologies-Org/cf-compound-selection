"use client";

import { createContext, useContext, useState, ReactNode } from "react";

interface AnalysisResult {
  compound: string;
  conclusion: string;
  rationale: string;
  runtime: string;
  confidence: number;
  relevance: number;
  toolTrace?: string | string[];
}

interface AnalysisContextType {
  result: AnalysisResult | null;
  setResult: (result: AnalysisResult) => void;
}

const AnalysisContext = createContext<AnalysisContextType | undefined>(
  undefined
);

export function AnalysisProvider({ children }: { children: ReactNode }) {
  const [result, setResult] = useState<AnalysisResult | null>(null);

  return (
    <AnalysisContext.Provider value={{ result, setResult }}>
      {children}
    </AnalysisContext.Provider>
  );
}

export function useAnalysis() {
  const context = useContext(AnalysisContext);
  if (context === undefined) {
    throw new Error("useAnalysis must be used within an AnalysisProvider");
  }
  return context;
}
