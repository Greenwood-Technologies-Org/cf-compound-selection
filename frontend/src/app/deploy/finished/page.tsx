"use client";

import { Button } from "@/components/ui/button";
import Navbar from "@/components/navbar";
export default function DeployPage2() {
  return (
    <main className="min-h-screen bg-gray-900 p-8 text-gray-100">
      <Navbar />

      <div className="mx-auto max-w-md rounded-md bg-white p-8 text-gray-900 shadow-md">
        <h2 className="mb-4 text-xl font-semibold">Deploy</h2>

        <div className="space-y-6">
          <div>
            <h3 className="text-sm font-semibold text-gray-700 uppercase">
              Runtime
            </h3>
            <p className="text-lg">Time to complete this task: 35 minutes</p>
          </div>

          <div>
            <h3 className="text-sm font-semibold text-gray-700 uppercase">
              Cost
            </h3>
            <p className="text-lg">Compute cost for this task: $2.36</p>
          </div>
        </div>

        <div className="mt-8 flex flex-col gap-4">
          <Button className="bg-black text-white hover:bg-gray-800">
            Download Output
          </Button>
          <Button className="bg-black text-white hover:bg-gray-800">
            Download Trajectory
          </Button>
        </div>
      </div>
    </main>
  );
}
