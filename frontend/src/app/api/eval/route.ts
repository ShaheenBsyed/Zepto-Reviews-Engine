import { NextResponse } from "next/server";
import path from "path";
import fs from "fs";

const OUTPUTS_DIR = path.join(process.cwd(), "public", "outputs");

export async function GET() {
  const filePath = path.join(OUTPUTS_DIR, "eval_report.json");

  if (!fs.existsSync(filePath)) {
    return NextResponse.json({
      phase: "Phase 6",
      passed: false,
      error: "No evaluation report found.",
    });
  }

  const raw = fs.readFileSync(filePath, "utf-8");
  const data = JSON.parse(raw);
  return NextResponse.json(data);
}
