import { NextResponse } from "next/server";
import path from "path";
import fs from "fs";

const OUTPUTS_DIR = path.join(process.cwd(), "public", "outputs");

export async function GET() {
  const filtersPath = path.join(OUTPUTS_DIR, "review_filters.json");

  if (fs.existsSync(filtersPath)) {
    const data = JSON.parse(fs.readFileSync(filtersPath, "utf-8"));
    return NextResponse.json(data);
  }

  return NextResponse.json({ sources: [], apps: [], ratings: [] });
}