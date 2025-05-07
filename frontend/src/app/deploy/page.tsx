"use client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";
import Navbar from "@/components/navbar";

function DeployContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const runtime = searchParams.get("runtime") || "N/A";
  const cost = searchParams.get("cost") || "N/A";
  const evaluationMetric = searchParams.get("metric") || "N/A";

  const handleDeploy = () => {
    router.push(
      `/deploy/finished?runtime=${encodeURIComponent(
        runtime
      )}&cost=${encodeURIComponent(cost)}&metric=${encodeURIComponent(
        evaluationMetric
      )}`
    );
  };

  return (
    <div className="mx-auto max-w-md rounded-md bg-white p-8 text-gray-900 shadow-md">
      <h2 className="mb-4 text-xl font-semibold">Deploy</h2>{" "}
      <div className="mb-6">
        <Label htmlFor="input-file" className="mb-1 block font-semibold">
          Input File
        </Label>
        <Input
          id="input-file"
          type="file"
          className="w-full"
          placeholder="Select Input File"
        />
      </div>
      <div className="flex justify-center">
        <Button
          className="bg-black text-white hover:bg-gray-800"
          onClick={handleDeploy}
        >
          Run
        </Button>
      </div>
    </div>
  );
}

export default function DeployPage() {
  return (
    <main className="min-h-screen bg-gray-900 p-8 text-gray-100">
      <Navbar />
      <Suspense fallback={<div>Loading...</div>}>
        <DeployContent />
      </Suspense>
    </main>
  );
}
