"use client";

import { Button } from "@/components/ui/button";
import Navbar from "@/components/navbar";
import { Suspense } from "react";
import { useAnalysis } from "@/context/AnalysisContext";
import { useRouter } from "next/navigation";

function formatToolCall(toolTrace: string | string[] | null | undefined) {
  if (!toolTrace) return "No tool call information available.";
  if (Array.isArray(toolTrace)) {
    if (toolTrace.length === 0) return "No tool call information available.";
    return (
      <ul className="list-disc pl-5">
        {toolTrace.map((trace, idx) => (
          <li key={idx} className="break-all">
            {trace}
          </li>
        ))}
      </ul>
    );
  }
  return toolTrace;
}

function ScoreBar({ value, label }: { value: number; label: string }) {
  const getColor = (value: number) => {
    if (value >= 80) return "bg-green-500";
    if (value >= 50) return "bg-yellow-500";
    return "bg-red-500";
  };

  return (
    <div className="mb-2">
      <div className="flex justify-between mb-1">
        <span className="text-sm font-medium text-gray-700">{label}</span>
        <span className="text-sm font-medium text-gray-700">{value}%</span>
      </div>
      <div className="w-full bg-gray-200 rounded-full h-2.5">
        <div
          className={`h-2.5 rounded-full ${getColor(value)}`}
          style={{ width: `${value}%` }}
        ></div>
      </div>
    </div>
  );
}

function ResultContent() {
  const router = useRouter();
  const { result } = useAnalysis();

  if (!result) {
    router.push("/analyze");
    return null;
  }

  return (
    <div className="mx-auto max-w-2xl rounded-xl bg-white p-8 text-gray-900 shadow-md">
      <h2 className="mb-6 text-2xl font-semibold">Analysis Results</h2>

      <div className="mb-4 rounded-md bg-gray-100 p-4">
        <h3 className="mb-1 font-semibold">Compound</h3>
        <p className="text-lg font-medium">{result.compound}</p>
      </div>

      <div className="mb-4 rounded-md bg-gray-100 p-4">
        <h3 className="mb-1 font-semibold">Conclusion</h3>
        <p className="text-lg font-medium">{result.conclusion}</p>
      </div>

      <div className="mb-4 rounded-md bg-gray-100 p-4">
        <h3 className="mb-1 font-semibold">Scores</h3>
        <div className="mt-2">
          <ScoreBar value={result.relevance} label="Relevance" />
          <ScoreBar value={result.confidence} label="Confidence" />
        </div>
      </div>

      <div className="mb-4 rounded-md bg-gray-100 p-4">
        <h3 className="mb-1 font-semibold">Tool Call</h3>
        <div className="whitespace-pre-line">
          {formatToolCall(result.toolTrace)}
        </div>
      </div>

      <div className="mb-4 rounded-md bg-gray-100 p-4">
        <h3 className="mb-1 font-semibold">Reasoning</h3>
        <p className="whitespace-pre-line">{result.rationale}</p>
      </div>

      <div className="flex flex-col md:flex-row md:items-center md:justify-between mt-8">
        <div>
          <span className="block text-sm font-medium text-gray-600">
            Analysis Time
          </span>
          <span className="text-base">{result.runtime}</span>
        </div>
        <Button
          onClick={() => router.push("/analyze")}
          className="mt-4 md:mt-0"
        >
          Analyze Another Compound
        </Button>
      </div>
    </div>
  );
}

function LoadingState() {
  return (
    <div className="mx-auto max-w-2xl rounded-md bg-white p-8 text-gray-900 shadow-md">
      <div className="flex items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-gray-300 border-t-blue-600"></div>
      </div>
    </div>
  );
}

export default function ResultPage() {
  return (
    <main className="min-h-screen bg-gray-900 p-8 text-gray-100">
      <Navbar />
      <Suspense fallback={<LoadingState />}>
        <ResultContent />
      </Suspense>
    </main>
  );
}
