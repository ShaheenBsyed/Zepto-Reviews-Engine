"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Insight, EvalReport } from "@/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { HelpCircle, Quote, Lightbulb, Loader2, TrendingUp } from "lucide-react";
import { cn, getConfidenceBadge, getConfidenceColor } from "@/lib/utils";
import { CardSkeleton } from "@/components/skeletons";

export default function QuestionsPage() {
  const [insights, setInsights] = useState<Insight[]>([]);
  const [evalReport, setEvalReport] = useState<EvalReport | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([api.insights(), api.eval()]).then(([insightsData, evalData]) => {
      setInsights(insightsData.insights || []);
      setEvalReport(evalData);
      setLoading(false);
    });
  }, []);

  if (loading) {
    return (
      <div className="space-y-6">
        {Array.from({ length: 3 }).map((_, i) => (
          <CardSkeleton key={i} />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h1 className="text-3xl font-bold text-slate-900 dark:text-white">Research Questions</h1>
        <p className="text-slate-500 dark:text-slate-400 mt-1">
          8 canonical research questions driving the analysis
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6">
        {insights.map((insight, idx) => {
          const hasEvidence = insight.evidence && insight.evidence.length > 0 && insight.evidence[0].quote;
          const faithfulness = evalReport?.faithfulness?.per_insight?.[insight.research_question_id];

          return (
            <Card
              key={insight.research_question_id}
              className="shadow-card hover-lift"
              style={{ animationDelay: `${idx * 50}ms` }}
            >
              <CardHeader className="pb-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-center gap-3">
                    <div className="p-2.5 rounded-xl bg-gradient-to-br from-primary/10 to-accent/10">
                      <HelpCircle className="w-5 h-5 text-primary" />
                    </div>
                    <div>
                      <CardTitle className="text-base font-semibold">
                        {insight.research_question_label}
                      </CardTitle>
                      <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                        {insight.finding.startsWith("Insufficient") ? "Insufficient evidence" : insight.finding}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {faithfulness && (
                      <Badge className={cn("text-xs font-medium", getConfidenceBadge(faithfulness.faithfulness_score))}>
                        {(faithfulness.faithfulness_score * 100).toFixed(0)}% faithful
                      </Badge>
                    )}
                    <Badge variant="secondary" className="text-xs">
                      {insight.research_question_id}
                    </Badge>
                  </div>
                </div>
              </CardHeader>

              {hasEvidence && (
                <CardContent className="space-y-4">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <div className="flex items-center gap-2">
                        <Quote className="w-4 h-4 text-primary" />
                        <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                          Retrieved Evidence
                        </p>
                      </div>
                      <div className="space-y-2">
                        {insight.evidence.slice(0, 2).map((ev, i) => (
                          <div
                            key={i}
                            className="p-3 rounded-xl bg-slate-50 dark:bg-slate-900 border border-slate-100 dark:border-slate-800"
                          >
                            <p className="text-xs text-slate-600 dark:text-slate-400 italic leading-relaxed">
                              "{ev.quote}"
                            </p>
                          </div>
                        ))}
                      </div>
                    </div>

                    <div className="space-y-3">
                      <div className="flex items-center gap-2">
                        <Lightbulb className="w-4 h-4 text-accent" />
                        <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                          Product Opportunity
                        </p>
                      </div>
                      <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed">
                        {insight.implication}
                      </p>

                      <div className="flex items-center gap-2 pt-2">
                        <TrendingUp className="w-4 h-4 text-primary" />
                        <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                          Customer Segment
                        </p>
                      </div>
                      <Badge variant="secondary" className="text-xs">
                        {insight.segment}
                      </Badge>
                    </div>
                  </div>
                </CardContent>
              )}
            </Card>
          );
        })}
      </div>
    </div>
  );
}
