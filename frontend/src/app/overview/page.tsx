"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Stats } from "@/types";
import { BarChart3, Database, FileText, FlaskConical, CheckCircle2, XCircle, Loader2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Bar, BarChart, ResponsiveContainer, XAxis, YAxis, Tooltip, PieChart, Pie, Cell } from "recharts";

const COLORS = ["#7c3aed", "#06b6d4", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899"];

export default function OverviewPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [distribution, setDistribution] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([api.stats(), api.reviewDistribution()]).then(([s, d]) => {
      setStats(s);
      setDistribution(d.by_rating || {});
      setLoading(false);
    });
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  const ratingData = [
    { name: "1 Star", value: Number(distribution["1"]) || 0, fill: "#ef4444" },
    { name: "2 Stars", value: Number(distribution["2"]) || 0, fill: "#f59e0b" },
    { name: "3 Stars", value: Number(distribution["3"]) || 0, fill: "#f97316" },
    { name: "4 Stars", value: Number(distribution["4"]) || 0, fill: "#22c55e" },
    { name: "5 Stars", value: Number(distribution["5"]) || 0, fill: "#06b6d4" },
  ];

  return (
    <div className="space-y-8 animate-fade-in">
      <div>
        <h1 className="text-3xl font-bold text-slate-900 dark:text-white">Pipeline Overview</h1>
        <p className="text-slate-500 dark:text-slate-400 mt-1">Monitor your AI Review Engine pipeline performance and data health</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard title="Raw Records" value={stats?.raw_records || 0} icon={Database} trend="+12%" trendUp />
        <KPICard title="Clean Chunks" value={stats?.clean_chunks || 0} icon={FileText} trend="+5%" trendUp />
         <KPICard title="Data Sources" value={stats?.sources.length || 0} icon={FlaskConical} names={stats?.sources} />
         <KPICard title="Apps Analyzed" value={stats?.apps.length || 0} icon={BarChart3} names={stats?.apps} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="shadow-card">
          <CardHeader>
            <CardTitle>Rating Distribution</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={ratingData}>
                <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip />
                <Bar dataKey="value" radius={[8, 8, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card className="shadow-card">
          <CardHeader>
            <CardTitle>Pipeline Health</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <HealthItem label="Insights Generated" passed={(stats?.total_insights || 0) >= 8} value={`${stats?.total_insights || 0}/8`} />
            <HealthItem label="Themes Identified" passed={(stats?.total_themes || 0) >= 8} value={`${stats?.total_themes || 0} themes`} />
            <div className="text-sm text-slate-500 dark:text-slate-400 pt-2 border-t border-slate-100 dark:border-slate-800">
              <p>Date Range: {stats?.date_range.earliest} — {stats?.date_range.latest}</p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function KPICard({ title, value, icon: Icon, trend, trendUp, names }: { title: string; value: number; icon: React.ElementType; trend?: string; trendUp?: boolean; names?: string[] }) {
  return (
    <Card className="shadow-card hover-lift">
      <CardContent className="p-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-slate-500 dark:text-slate-400">{title}</p>
            <p className="text-3xl font-bold text-slate-900 dark:text-white mt-1">{value.toLocaleString()}</p>
            {names && names.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mt-2">
                {names.map((name) => (
                  <span
                    key={name}
                    className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300"
                  >
                    {name}
                  </span>
                ))}
              </div>
            )}
            {trend && (
              <p className={`text-xs font-medium mt-1 ${trendUp ? "text-emerald-500" : "text-red-500"}`}>
                {trend} from last run
              </p>
            )}
          </div>
          <div className="p-3 rounded-2xl bg-primary/10 dark:bg-primary/20">
            <Icon className="w-6 h-6 text-primary" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function HealthItem({ label, passed, value }: { label: string; passed: boolean; value?: string }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-sm text-slate-600 dark:text-slate-400">{label}</span>
      <div className="flex items-center gap-2">
        {value && <span className="text-sm font-medium text-slate-900 dark:text-white">{value}</span>}
        {passed ? <CheckCircle2 className="w-5 h-5 text-emerald-500" /> : <XCircle className="w-5 h-5 text-red-500" />}
      </div>
    </div>
  );
}
