import { NextResponse } from "next/server";
import path from "path";
import fs from "fs";

const OUTPUTS_DIR = path.join(process.cwd(), "public", "outputs");

export async function GET(request: Request) {
  const url = new URL(request.url);
  const search = url.searchParams.get("search") || "";
  const source = url.searchParams.get("source") || "";
  const app = url.searchParams.get("app") || "";
  const rating = url.searchParams.get("rating") || "";
  const page = parseInt(url.searchParams.get("page") || "1", 10);
  const pageSize = Math.min(parseInt(url.searchParams.get("page_size") || "25", 10), 200);

  const reviewsPath = path.join(OUTPUTS_DIR, "reviews_export.json");

  if (!fs.existsSync(reviewsPath)) {
    return NextResponse.json({
      data: [],
      count: 0,
      total: 0,
      page,
      page_size: pageSize,
    });
  }

  const allReviews: Array<{
    source: string;
    app: string;
    text: string;
    rating: number;
    date: string;
    language: string;
  }> = JSON.parse(fs.readFileSync(reviewsPath, "utf-8"));

  let filtered = allReviews;

  if (source) {
    filtered = filtered.filter((r) => r.source === source);
  }
  if (app) {
    filtered = filtered.filter((r) => r.app === app);
  }
  if (rating) {
    filtered = filtered.filter((r) => r.rating === parseInt(rating, 10));
  }
  if (search) {
    const lower = search.toLowerCase();
    filtered = filtered.filter(
      (r) =>
        (r.text && r.text.toLowerCase().includes(lower)) ||
        (r.source && r.source.toLowerCase().includes(lower)) ||
        (r.app && r.app.toLowerCase().includes(lower))
    );
  }

  const total = filtered.length;
  const start = (page - 1) * pageSize;
  const data = filtered.slice(start, start + pageSize);

  return NextResponse.json({
    data,
    count: data.length,
    total,
    page,
    page_size: pageSize,
  });
}