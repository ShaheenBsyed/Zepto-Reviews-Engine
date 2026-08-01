import { NextResponse } from "next/server";
import path from "path";
import fs from "fs";

const OUTPUTS_DIR = path.join(process.cwd(), "public", "outputs");

export async function GET() {
  const insightsPath = path.join(OUTPUTS_DIR, "insights.json");

  if (!fs.existsSync(insightsPath)) {
    return NextResponse.json({ segments: [], count: 0 });
  }

  const raw = fs.readFileSync(insightsPath, "utf-8");
  const data = JSON.parse(raw);

  const segments: Record<string, {
    segment: string;
    insights: Array<{
      research_question_id: string;
      research_question_label: string;
      finding: string;
      implication: string;
      confidence: number;
    }>;
    research_questions: string[];
    average_confidence: number;
    evidence_count: number;
    insight_count: number;
  }> = {};

  for (const insight of data.insights || []) {
    const segment = insight.segment || "Unknown";
    if (!segment || segment === "Unknown") continue;

    if (!segments[segment]) {
      segments[segment] = {
        segment,
        insights: [],
        research_questions: [],
        average_confidence: 0,
        evidence_count: 0,
        insight_count: 0,
      };
    }

    segments[segment].insights.push({
      research_question_id: insight.research_question_id,
      research_question_label: insight.research_question_label,
      finding: insight.finding,
      implication: insight.implication,
      confidence: insight.confidence || 0,
    });
    segments[segment].research_questions.push(insight.research_question_label);
    segments[segment].evidence_count += (insight.evidence?.length || 0);
  }

  const segmentList = Object.values(segments).map((seg) => {
    const confidences = seg.insights
      .map((i) => i.confidence)
      .filter((c): c is number => c !== null && c !== undefined);
    return {
      ...seg,
      average_confidence:
        confidences.length > 0
          ? Math.round((confidences.reduce((a, b) => a + b, 0) / confidences.length) * 100) / 100
          : 0,
      insight_count: seg.insights.length,
    };
  });

  return NextResponse.json({ segments: segmentList, count: segmentList.length });
}
