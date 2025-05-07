"use client";

import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import Navbar from "@/components/navbar";
import { useState } from "react";
import { useAnalysis } from "@/context/AnalysisContext";
import toast from "react-hot-toast";

export default function AnalyzePage() {
  const router = useRouter();
  const { setResult } = useAnalysis();
  const [isLoading, setIsLoading] = useState(false);
  const [drugName, setDrugName] = useState("");

  const handleAnalyze = async () => {
    setIsLoading(true);
    const startTime = performance.now();

    try {
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_BACKEND_URL}/analyze_fibrosis`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            drug_name: drugName,
          }),
        }
      );

      if (!response.ok) {
        const errorData = await response.json().catch(() => null);
        throw new Error(errorData?.detail || "Failed to analyze compound");
      }

      const data = await response.json();
      console.log("Analysis Response:", {
        conclusion: data.conclusion,
        relevance: data.relevance,
        confidence: data.confidence,
        rationale: data.rationale,
        tool_trace: data.tool_trace,
      });

      const endTime = performance.now();

      const runtimeMs = endTime - startTime;
      let runtimeDisplay;
      if (runtimeMs < 1000) {
        runtimeDisplay = `${runtimeMs.toFixed(0)}ms`;
      } else if (runtimeMs < 60000) {
        runtimeDisplay = `${(runtimeMs / 1000).toFixed(2)}s`;
      } else {
        const minutes = Math.floor(runtimeMs / 60000);
        const seconds = ((runtimeMs % 60000) / 1000).toFixed(0);
        runtimeDisplay = `${minutes}m ${seconds}s`;
      }

      setResult({
        compound: drugName,
        conclusion: data.conclusion,
        rationale: data.rationale,
        runtime: runtimeDisplay,
        confidence: data.confidence,
        relevance: data.relevance,
        toolTrace: data.tool_trace,
      });

      router.push("/analyze/result");
    } catch (error) {
      console.error("Error:", error);
      toast.error(
        error instanceof Error ? error.message : "An unexpected error occurred"
      );
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-gray-900 p-8 text-gray-100">
      <Navbar />

      <div className="mx-auto max-w-2xl rounded-md bg-white p-8 text-gray-900 shadow-md">
        <h2 className="mb-4 text-xl font-semibold">
          Analyze Compound Effect on Cardiac Fibrosis
        </h2>

        <div className="space-y-4">
          <div>
            <Label htmlFor="drug-name" className="mb-1 block font-semibold">
              Compound Name
            </Label>
            <Input
              id="drug-name"
              placeholder="Enter compound name (e.g., JQ1)"
              className="mt-1"
              value={drugName}
              onChange={(e) => setDrugName(e.target.value)}
            />
          </div>

          <div className="flex justify-end">
            <Button
              className="mt-4"
              onClick={handleAnalyze}
              disabled={isLoading || !drugName}
            >
              {isLoading ? "Analyzing..." : "Analyze Compound"}
            </Button>
          </div>
        </div>
      </div>
    </main>
  );
}
