import { NextResponse } from "next/server";
import path from "path";
import fs from "fs";

const OUTPUTS_DIR = path.join(process.cwd(), "public", "outputs");

export async function GET(request: Request) {
  const url = new URL(request.url);
  const fmt = url.searchParams.get("format") || "json";

  const umapPath = path.join(OUTPUTS_DIR, "umap_coords.json");
  const imagePath = path.join(OUTPUTS_DIR, "umap_clusters.png");

  if (fmt === "image") {
    const exists = fs.existsSync(imagePath);
    return NextResponse.json({
      exists,
      image_url: exists ? "/outputs/umap_clusters.png" : undefined,
    });
  }

  if (fs.existsSync(umapPath)) {
    const data = JSON.parse(fs.readFileSync(umapPath, "utf-8"));
    return NextResponse.json(data);
  }

  return NextResponse.json({ points: [], count: 0 });
}