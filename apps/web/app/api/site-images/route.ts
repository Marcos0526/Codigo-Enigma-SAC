import { readdir, stat } from "node:fs/promises";
import path from "node:path";
import { NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  const directory = path.join(process.cwd(), "public", "images");
  let files: string[];
  try {
    files = (await readdir(directory)).sort();
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
    files = [];
  }

  async function findImage(name: string) {
    const file = files.find((file) =>
      new RegExp(`^${name}\\.(svg|png|jpe?g|webp|avif|gif)$`, "i").test(file),
    );
    if (!file) return null;
    const info = await stat(path.join(directory, file));
    if (!info.isFile()) return null;
    return `/images/${encodeURIComponent(file)}?v=${info.mtimeMs}`;
  }

  const [logo, background] = await Promise.all([
    findImage("logo"),
    findImage("background"),
  ]);
  return NextResponse.json(
    { logo, background },
    { headers: { "Cache-Control": "no-store" } },
  );
}
