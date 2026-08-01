"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Segment } from "@/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Users, TrendingUp, Quote, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { CardSkeleton } from "@/components/skeletons";

const AVATAR_COLORS = [
  "from-violet-500 to-purple-600",
  "from-cyan-500 to-blue-600",
  "from-amber-500 to-orange-600",
  "from-emerald-500 to-teal-600",
  "from-pink-500 to-rose-600",
  "from-indigo-500 to-violet-600",
];

export default function SegmentsPage() {
  const [segments, setSegments] = useState<Segment[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.segments().then((data) => {
      setSegments(data.segments || []);
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

  if (segments.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-96 text-center">
        <div className="p-4 rounded-full bg-slate-100 dark:bg-slate-800 mb-4">
          <Users className="w-8 h-8 text-slate-400" />
        </div>
        <h3 className="text-lg font-semibold text-slate-900 dark:text-white">No segments yet</h3>
        <p className="text-slate-500 dark:text-slate-400 mt-1">Run Phase 5 to generate customer segment profiles.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h1 className="text-3xl font-bold text-slate-900 dark:text-white">Customer Segments</h1>
        <p className="text-slate-500 dark:text-slate-400 mt-1">
          {segments.length} distinct user personas identified from reviews
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {segments.map((segment, idx) => {
          const avatarColor = AVATAR_COLORS[idx % AVATAR_COLORS.length];
          const initials = segment.segment
            .split(" ")
            .map((w) => w[0])
            .join("")
            .slice(0, 2)
            .toUpperCase();

          return (
            <Card
              key={segment.segment}
              className="shadow-card hover-lift group"
              style={{ animationDelay: `${idx * 50}ms` }}
            >
              <CardHeader className="pb-3">
                <div className="flex items-center gap-3">
                  <div className={`w-12 h-12 rounded-2xl bg-gradient-to-br ${avatarColor} flex items-center justify-center text-white font-bold text-lg shadow-lg`}>
                    {initials}
                  </div>
                  <div>
                    <CardTitle className="text-base font-semibold group-hover:text-primary transition-colors">
                      {segment.segment}
                    </CardTitle>
                    <div className="flex items-center gap-2 mt-1">
                      <Badge variant="secondary" className="text-xs">
                        {segment.insight_count} insights
                      </Badge>
                      <Badge className={cn("text-xs", segment.average_confidence >= 0.7 ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700")}>
                        {(segment.average_confidence * 100).toFixed(0)}% avg confidence
                      </Badge>
                    </div>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-2">
                    Research Questions
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {segment.research_questions.slice(0, 4).map((rq, i) => (
                      <Badge key={i} variant="outline" className="text-xs">
                        {rq}
                      </Badge>
                    ))}
                    {segment.research_questions.length > 4 && (
                      <Badge variant="outline" className="text-xs">
                        +{segment.research_questions.length - 4} more
                      </Badge>
                    )}
                  </div>
                </div>

                <div className="space-y-2">
                  <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                    Key Findings
                  </p>
                  {segment.insights.slice(0, 2).map((insight, i) => (
                    <div
                      key={i}
                      className="flex items-start gap-2 p-3 rounded-xl bg-slate-50 dark:bg-slate-900 border border-slate-100 dark:border-slate-800"
                    >
                      <Quote className="w-4 h-4 text-lavender-400 mt-0.5 shrink-0" />
                      <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed line-clamp-2">
                        {insight.finding}
                      </p>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
