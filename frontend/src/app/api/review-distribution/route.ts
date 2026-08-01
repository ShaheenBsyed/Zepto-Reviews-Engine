import { NextResponse } from "next/server";
import path from "path";
import fs from "fs";

const OUTPUTS_DIR = path.join(process.cwd(), "public", "outputs");

export async function GET() {
  const distPath = path.join(OUTPUTS_DIR, "review_distribution.json");

  if (fs.existsSync(distPath)) {
    const data = JSON.parse(fs.readFileSync(distPath, "utf-8"));
    return NextResponse.json(data);
  }

  return NextResponse.json({ by_source: {}, by_app: {}, by_rating: {} });
}