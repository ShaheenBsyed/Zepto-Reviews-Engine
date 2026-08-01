"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Theme } from "@/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Quote, Hash, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { CardSkeleton } from "@/components/skeletons";

export default function ThemesPage() {
  const [themes, setThemes] = useState<Theme[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.themes().then((data) => {
      setThemes(data.themes || []);
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

  if (themes.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-96 text-center">
        <div className="p-4 rounded-full bg-slate-100 dark:bg-slate-800 mb-4">
          <Hash className="w-8 h-8 text-slate-400" />
        </div>
        <h3 className="text-lg font-semibold text-slate-900 dark:text-white">No themes yet</h3>
        <p className="text-slate-500 dark:text-slate-400 mt-1">Run Phase 4 to discover themes in your review corpus.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h1 className="text-3xl font-bold text-slate-900 dark:text-white">Theme Explorer</h1>
        <p className="text-slate-500 dark:text-slate-400 mt-1">
          {themes.length} themes discovered from customer reviews
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {themes.map((theme, idx) => {
          const validQuotes = (theme.quotes || []).filter((q) => q && q.trim().length > 0);
          const displayName = theme.theme_name || `Theme ${theme.cluster_id + 1}`;

          return (
            <Card
              key={theme.cluster_id}
              className="shadow-card hover-lift group"
              style={{ animationDelay: `${idx * 50}ms` }}
            >
              <CardHeader className="pb-3">
                <div className="flex items-center gap-2 mb-2">
                  <div className="p-2 rounded-xl bg-gradient-to-br from-primary/10 to-accent/10">
                    <Hash className="w-4 h-4 text-primary" />
                  </div>
                  <Badge variant="secondary" className="text-xs">
                    {theme.num_samples || 0} samples
                  </Badge>
                </div>
                <div className="flex flex-wrap gap-2 mb-2">
                  {theme.category && (
                    <Badge variant="outline" className="text-xs">
                      {theme.category}
                    </Badge>
                  )}
                  {theme.barrier && (
                    <Badge variant="destructive" className="text-xs">
                      {theme.barrier}
                    </Badge>
                  )}
                </div>
                <CardTitle className="text-base font-semibold group-hover:text-primary transition-colors">
                  {displayName}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <p className="text-sm text-slate-600 dark:text-slate-400 leading-relaxed">
                  {theme.description || "No description available."}
                </p>

                {validQuotes.length > 0 && (
                  <div className="space-y-2">
                    <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                      Representative Quotes
                    </p>
                    {validQuotes.slice(0, 3).map((quote, i) => (
                      <div
                        key={i}
                        className="flex items-start gap-2 p-3 rounded-xl bg-slate-50 dark:bg-slate-900 border border-slate-100 dark:border-slate-800"
                      >
                        <Quote className="w-4 h-4 text-lavender-400 mt-0.5 shrink-0" />
                        <p className="text-xs text-slate-600 dark:text-slate-400 italic leading-relaxed">"{quote}"</p>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
