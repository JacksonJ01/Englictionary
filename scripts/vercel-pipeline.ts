import { access, copyFile, mkdir, readFile, writeFile } from "node:fs/promises";
import { constants } from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

const ROOT = process.cwd();
const OUTPUT_DIR = path.join(ROOT, "output");
const SPHERICAL_DIR = path.join(OUTPUT_DIR, "spherical");
const RUN_METADATA_FILE = path.join(OUTPUT_DIR, "run_metadata.json");
const TARGET_HTML = path.join(SPHERICAL_DIR, "Englictionary.html");
const DEPLOY_INDEX = path.join(OUTPUT_DIR, "index.html");
const SPHERICAL_ROUTE_INDEX = path.join(SPHERICAL_DIR, "index.html");

export async function exists(filePath: string): Promise<boolean> {
  try {
    await access(filePath, constants.F_OK);
    return true;
  } catch {
    return false;
  }
}

async function readMetadataPlotFile(): Promise<string | null> {
  if (!(await exists(RUN_METADATA_FILE))) {
    return null;
  }

  try {
    const raw = await readFile(RUN_METADATA_FILE, "utf8");
    const parsed = JSON.parse(raw) as { plot_file?: string };
    if (!parsed.plot_file) {
      return null;
    }

    const absolute = path.isAbsolute(parsed.plot_file)
      ? parsed.plot_file
      : path.join(ROOT, parsed.plot_file);

    return (await exists(absolute)) ? absolute : null;
  } catch {
    return null;
  }
}

async function chooseSourceHtml(): Promise<string | null> {
  const fromMetadata = await readMetadataPlotFile();
  if (fromMetadata) {
    return fromMetadata;
  }

  const candidates = [
    path.join(SPHERICAL_DIR, "Englictionary.html"),
    path.join(SPHERICAL_DIR, "CompTIAA+Study.html"),
    path.join(SPHERICAL_DIR, "CompTIA_A+_Study.html")
  ];

  for (const candidate of candidates) {
    if (await exists(candidate)) {
      return candidate;
    }
  }

  return null;
}

function buildFallbackHtml(): string {
  return "<!doctype html><html><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>Englictionary</title></head><body><h1>Englictionary output is not available yet</h1><p>Run the pipeline locally to generate output/spherical/Englictionary.html.</p></body></html>";
}

async function ensureIndexRedirect(): Promise<void> {
  const html = "<!doctype html><html><head><meta charset=\"utf-8\"><meta http-equiv=\"refresh\" content=\"0; url=/spherical\"><title>Redirecting</title></head><body><p>Redirecting to <a href=\"/spherical\">/spherical</a>...</p></body></html>";
  await writeFile(DEPLOY_INDEX, html, "utf8");
}

async function ensureSphericalRoute(targetHtml: string): Promise<void> {
  await copyFile(targetHtml, SPHERICAL_ROUTE_INDEX);
}

export async function prepareVercelArtifacts(): Promise<{ targetHtml: string; sourceHtml: string | null }> {
  await mkdir(SPHERICAL_DIR, { recursive: true });

  const sourceHtml = await chooseSourceHtml();
  if (sourceHtml) {
    if (path.resolve(sourceHtml) !== path.resolve(TARGET_HTML)) {
      await copyFile(sourceHtml, TARGET_HTML);
    }
    console.log(`Prepared deploy HTML: ${TARGET_HTML}`);
  } else {
    await writeFile(TARGET_HTML, buildFallbackHtml(), "utf8");
    console.warn("No spherical output HTML found; wrote fallback page.");
  }

  await ensureIndexRedirect();
  console.log("Prepared index redirect for Vercel root route.");

  await ensureSphericalRoute(TARGET_HTML);
  console.log("Prepared /spherical route at output/spherical/index.html.");

  return {
    targetHtml: TARGET_HTML,
    sourceHtml,
  };
}

const entryFile = process.argv[1] ? pathToFileURL(process.argv[1]).href : "";

if (import.meta.url === entryFile) {
  await prepareVercelArtifacts();
}
