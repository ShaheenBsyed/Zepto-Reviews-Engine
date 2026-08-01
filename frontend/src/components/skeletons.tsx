import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function CardSkeleton() {
  return (
    <Card className="shadow-card">
      <CardHeader>
        <div className="skeleton h-6 w-3/4 rounded-lg" />
        <div className="skeleton h-4 w-1/2 rounded-lg mt-2" />
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          <div className="skeleton h-4 w-full rounded-lg" />
          <div className="skeleton h-4 w-5/6 rounded-lg" />
          <div className="skeleton h-4 w-4/6 rounded-lg" />
        </div>
      </CardContent>
    </Card>
  );
}

export function ChartSkeleton() {
  return (
    <Card className="shadow-card">
      <CardHeader>
        <div className="skeleton h-6 w-1/3 rounded-lg" />
      </CardHeader>
      <CardContent>
        <div className="skeleton h-[300px] w-full rounded-lg" />
      </CardContent>
    </Card>
  );
}

export function TableSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="skeleton h-12 w-full rounded-lg" />
      ))}
    </div>
  );
}
