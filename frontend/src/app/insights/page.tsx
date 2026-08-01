"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Insight } from "@/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ChevronDown, ChevronUp, Quote, Target, Users, Lightbulb, TrendingUp } from "lucide-react";
import { cn, getConfidenceBadge, getConfidenceColor } from "@/lib/utils";
import { CardSkeleton } from "@/components/skeletons";

export default function InsightsPage() {
  const [insights, setInsights] = useState<Insight[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  useEffect(() => {
    api.insights().then((data) => {
      const valid = data.insights.filter(
        (i) => i.finding && !i.finding.startsWith("Insufficient") && i.evidence && i.evidence.length > 0
      );
      setInsights(valid);
      setLoading(false);
    });
  }, []);

  if (loading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {Array.from({ length: 6 }).map((_, i) => (
          <CardSkeleton key={i} />
        ))}
      </div>
    );
  }

  if (insights.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-96 text-center">
        <div className="p-4 rounded-full bg-slate-100 dark:bg-slate-800 mb-4">
          <Lightbulb className="w-8 h-8 text-slate-400" />
        </div>
        <h3 className="text-lg font-semibold text-slate-900 dark:text-white">No insights yet</h3>
        <p className="text-slate-500 dark:text-slate-400 mt-1">Run Phase 5 to generate AI-powered insights from your reviews.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h1 className="text-3xl font-bold text-slate-900 dark:text-white">AI Insights</h1>
        <p className="text-slate-500 dark:text-slate-400 mt-1">Evidence-backed findings from your customer reviews</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {insights.map((insight, idx) => {
          const isExpanded = expandedId === `${insight.research_question_id}-${idx}`;
          const hasEvidence = insight.evidence && insight.evidence.length > 0 && insight.evidence[0].quote;

          if (!hasEvidence) return null;

          return (
            <Card
              key={insight.research_question_id}
              className="shadow-card hover-lift cursor-pointer group"
              onClick={() => setExpandedId(isExpanded ? null : `${insight.research_question_id}-${idx}`)}
            >
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between gap-2">
                  <CardTitle className="text-base font-semibold leading-tight group-hover:text-primary transition-colors">
                    {insight.finding}
                  </CardTitle>
                  {isExpanded ? <ChevronUp className="w-5 h-5 text-slate-400 shrink-0" /> : <ChevronDown className="w-5 h-5 text-slate-400 shrink-0" />}
                </div>
                <div className="flex items-center gap-2 mt-2">
                  <Badge variant="secondary" className="text-xs">
                    {insight.research_question_label}
                  </Badge>
                  <Badge className={cn("text-xs font-medium", getConfidenceBadge(insight.confidence))}>
                    {(insight.confidence * 100).toFixed(0)}% confidence
                  </Badge>
                </div>
              </CardHeader>

              {isExpanded && (
                <CardContent className="pt-0 space-y-4 animate-scale-in">
                  <div className="space-y-3">
                    <div className="flex items-start gap-2">
                      <Target className="w-4 h-4 text-primary mt-0.5 shrink-0" />
                      <div>
                        <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">Product Opportunity</p>
                        <p className="text-sm text-slate-700 dark:text-slate-300 mt-1">{insight.implication}</p>
                      </div>
                    </div>

                    <div className="flex items-start gap-2">
                      <Users className="w-4 h-4 text-accent mt-0.5 shrink-0" />
                      <div>
                        <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">Customer Segment</p>
                        <p className="text-sm text-slate-700 dark:text-slate-300 mt-1">{insight.segment}</p>
                      </div>
                    </div>

                    <div>
                      <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-2">Supporting Evidence</p>
                      <div className="space-y-2">
                        {insight.evidence.slice(0, 3).map((ev, i) => (
                          <div key={i} className="flex items-start gap-2 p-3 rounded-xl bg-slate-50 dark:bg-slate-900 border border-slate-100 dark:border-slate-800">
                            <Quote className="w-4 h-4 text-lavender-400 mt-0.5 shrink-0" />
                            <p className="text-xs text-slate-600 dark:text-slate-400 italic leading-relaxed">"{ev.quote}"</p>
                          </div>
                        ))}
                      </div>
                    </div>

                    {insight.faithfulness_score !== undefined && (
                      <div className="flex items-center gap-2 pt-2 border-t border-slate-100 dark:border-slate-800">
                        <TrendingUp className="w-4 h-4 text-slate-400" />
                        <span className="text-xs text-slate-500 dark:text-slate-400">
                          Faithfulness: <span className={cn("font-medium", getConfidenceColor(insight.faithfulness_score))}>
                            {(insight.faithfulness_score * 100).toFixed(0)}%
                          </span> ({insight.faithfulness_judge})
                        </span>
                      </div>
                    )}
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
