import { readFile } from "node:fs/promises";
import path from "node:path";
import { NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const datasets = [
  {
    id: "psi-20-bre-temperature-csv",
    title: "BRE Flame Temperature Measurements",
    filename: "psi-20-bre-temperature-csv.csv"
  },
  {
    id: "psi-21-cld-soot-csv",
    title: "CLD Flame Soot Volume Fraction",
    filename: "psi-21-cld-soot-csv.csv"
  },
  {
    id: "psi-69-flex-droplet-extinction-csv",
    title: "FLEX Droplet Extinction Measurements",
    filename: "psi-69-flex-droplet-extinction-csv.csv"
  },
  {
    id: "psi-39-cfi-cool-flame-csv",
    title: "CFI Cool Flame Droplet Temperature",
    filename: "psi-39-cfi-cool-flame-csv.csv"
  },
  {
    id: "psi-107-spice-smoke-point-csv",
    title: "SPICE Smoke Point and Flame Length",
    filename: "psi-107-spice-smoke-point-csv.csv"
  },
  {
    id: "psi-26-bass-solid-flame-spread-csv",
    title: "BASS Solid Fuel Flame Spread Rates",
    filename: "psi-26-bass-solid-flame-spread-csv.csv"
  },
  {
    id: "psi-102-same-smoke-aerosol-csv",
    title: "SAME Smoke Aerosol Size Distribution",
    filename: "psi-102-same-smoke-aerosol-csv.csv"
  },
  {
    id: "psi-98-saffire-i-fabric-burn-csv",
    title: "SAFFIRE-I Fabric Burn Sensor Data",
    filename: "psi-98-saffire-i-fabric-burn-csv.csv"
  },
  {
    id: "psi-159-cfig-gaseous-cool-flame-csv",
    title: "CFI-G Gaseous Cool Flame",
    filename: "psi-159-cfig-gaseous-cool-flame-csv.csv"
  },
  {
    id: "psi-106-slice-liftoff-csv",
    title: "SLICE Flame Liftoff and Structure",
    filename: "psi-106-slice-liftoff-csv.csv"
  }
] as const;

function parseCsv(csv: string): Array<Record<string, string | number | null>> {
  const records: string[][] = [];
  let record: string[] = [];
  let field = "";
  let quoted = false;

  for (let index = 0; index < csv.length; index += 1) {
    const character = csv[index];
    if (quoted) {
      if (character === '"' && csv[index + 1] === '"') {
        field += '"';
        index += 1;
      } else if (character === '"') {
        quoted = false;
      } else {
        field += character;
      }
    } else if (character === '"') {
      quoted = true;
    } else if (character === ",") {
      record.push(field);
      field = "";
    } else if (character === "\n") {
      record.push(field.replace(/\r$/, ""));
      records.push(record);
      record = [];
      field = "";
    } else {
      field += character;
    }
  }

  if (field.length > 0 || record.length > 0) {
    record.push(field.replace(/\r$/, ""));
    records.push(record);
  }

  const [header, ...rows] = records;
  if (!header?.length) {
    throw new Error("The synthetic CSV file has no header row.");
  }

  return rows
    .filter((row) => row.some((value) => value !== ""))
    .map((row) =>
      Object.fromEntries(
        header.map((column, index) => {
          const value = row[index] ?? "";
          if (value === "") return [column, null];
          const numericValue = Number(value);
          return [column, Number.isFinite(numericValue) ? numericValue : value];
        })
      )
    );
}

export async function GET(request: Request) {
  const datasetId = new URL(request.url).searchParams.get("dataset");

  if (!datasetId) {
    return NextResponse.json(
      datasets.map(({ id, title }) => ({
        id,
        title,
        investigation: id.match(/^psi-\d+/)?.[0] ?? "PSI"
      }))
    );
  }

  const dataset = datasets.find((item) => item.id === datasetId);
  if (!dataset) {
    return NextResponse.json({ error: "Synthetic dataset not found." }, { status: 404 });
  }

  const dataDirectory =
    process.env.SYNTHETIC_DATA_DIR ?? path.resolve(process.cwd(), "../../data/synthetic");
  const csv = await readFile(path.join(dataDirectory, dataset.filename), "utf8");
  const rows = parseCsv(csv);
  const columns = Object.keys(rows[0] ?? {});

  return NextResponse.json({
    id: dataset.id,
    title: dataset.title,
    columns,
    rows
  });
}
