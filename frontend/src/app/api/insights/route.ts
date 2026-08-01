import { NextResponse } from "next/server";
import path from "path";
import fs from "fs";

const OUTPUTS_DIR = path.join(process.cwd(), "public", "outputs");

export async function GET() {
  const filePath = path.join(OUTPUTS_DIR, "insights.json");

  if (!fs.existsSync(filePath)) {
    return NextResponse.json({ insights: [], count: 0 });
  }

  const raw = fs.readFileSync(filePath, "utf-8");
  const data = JSON.parse(raw);

  const evalPath = path.join(OUTPUTS_DIR, "eval_report.json");
  if (fs.existsSync(evalPath)) {
    try {
      const evalRaw = fs.readFileSync(evalPath, "utf-8");
      const evalData = JSON.parse(evalRaw);
      const perInsight = evalData.faithfulness?.per_insight || {};
      for (const insight of data.insights || []) {
        const qid = insight.research_question_id || "";
        const scoreInfo = perInsight[qid] || {};
        insight.faithfulness_score = scoreInfo.faithfulness_score;
        insight.faithfulness_passed = scoreInfo.faithfulness_passed;
        insight.faithfulness_judge = scoreInfo.judge;
      }
    } catch {
      // ignore eval read errors
    }
  }

  return NextResponse.json(data);
}
