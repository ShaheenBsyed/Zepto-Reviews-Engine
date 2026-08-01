import { NextResponse } from "next/server";
import path from "path";
import fs from "fs";

const OUTPUTS_DIR = path.join(process.cwd(), "public", "outputs");

export async function GET() {
  const filePath = path.join(OUTPUTS_DIR, "themes.json");

  if (!fs.existsSync(filePath)) {
    return NextResponse.json({ themes: [], count: 0 });
  }

  const raw = fs.readFileSync(filePath, "utf-8");
  const data = JSON.parse(raw);
  const themes = Array.isArray(data) ? data : data.themes || [];

  return NextResponse.json({ themes, count: themes.length });
}