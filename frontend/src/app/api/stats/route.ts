import { NextResponse } from "next/server";
import path from "path";
import fs from "fs";

const OUTPUTS_DIR = path.join(process.cwd(), "public", "outputs");
const DATA_DIR = path.join(process.cwd(), "public", "outputs");

export async function GET() {
  const stats = {
    phase: "Phase 7 - Dashboard & Deployment",
    raw_records: 0,
    clean_chunks: 0,
    sources: [] as string[],
    apps: [] as string[],
    date_range: { earliest: null as string | null, latest: null as string | null },
    total_insights: 0,
    total_themes: 0,
    eval_passed: false,
  };

  const reportPath = path.join(OUTPUTS_DIR, "ingestion_report.json");
  if (fs.existsSync(reportPath)) {
    const report = JSON.parse(fs.readFileSync(reportPath, "utf-8"));
    stats.raw_records = report.total_records_in_store || 0;
    stats.sources = Object.keys(report.records_by_source || {});
    stats.apps = Object.keys(report.records_by_app || {});
    stats.date_range = report.date_range || { earliest: null, latest: null };
  }

  const chunksPath = path.join(DATA_DIR, "processed", "clean_chunks.jsonl");
  if (fs.existsSync(chunksPath)) {
    let chunkCount = 0;
    const content = fs.readFileSync(chunksPath, "utf-8");
    for (const line of content.split("\n")) {
      const trimmed = line.trim();
      if (trimmed && !trimmed.startsWith("#")) {
        chunkCount++;
      }
    }
    stats.clean_chunks = chunkCount;
  }

  const insightsPath = path.join(OUTPUTS_DIR, "insights.json");
  if (fs.existsSync(insightsPath)) {
    const data = JSON.parse(fs.readFileSync(insightsPath, "utf-8"));
    stats.total_insights = (data.insights || []).length;
  }

  const themesPath = path.join(OUTPUTS_DIR, "themes.json");
  if (fs.existsSync(themesPath)) {
    const data = JSON.parse(fs.readFileSync(themesPath, "utf-8"));
    stats.total_themes = Array.isArray(data) ? data.length : (data.themes || []).length;
  }

  const evalPath = path.join(OUTPUTS_DIR, "eval_report.json");
  if (fs.existsSync(evalPath)) {
    const data = JSON.parse(fs.readFileSync(evalPath, "utf-8"));
    stats.eval_passed = data.passed || false;
  }

  return NextResponse.json(stats);
}