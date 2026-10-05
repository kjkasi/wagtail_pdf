import { copyFile, cp, mkdir, readFile, writeFile } from "node:fs/promises";
import { basename, dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
// Keep main, worker and annotation resources on the same legacy distribution.
// Add the Firefox 115 compatibility layer to both executable assets.
const buildSource = resolve(root, "node_modules/pdfjs-dist/legacy/build");
const webSource = resolve(root, "node_modules/pdfjs-dist/legacy/web");
const destination = resolve(root, "catalog/static/catalog/vendor/pdfjs");
const compatibilitySource = await readFile(
  resolve(root, "scripts/pdfjs-compatibility.js"),
  "utf8",
);
const licenseEnd = " * @licend The above is the entire license notice for the\n * JavaScript code in this page\n */\n";

function addCompatibility(source) {
  const licenseEndIndex = source.indexOf(licenseEnd);
  if (licenseEndIndex === -1) {
    throw new Error("PDF.js license marker not found");
  }
  const insertionPoint = licenseEndIndex + licenseEnd.length;
  return `${source.slice(0, insertionPoint)}\n${compatibilitySource}\n${source.slice(insertionPoint)}`;
}

async function copyPdfjsAsset(source, target) {
  const contents = await readFile(source, "utf8");
  await writeFile(target, addCompatibility(contents));
}

await mkdir(destination, { recursive: true });
await Promise.all([
  copyPdfjsAsset(resolve(buildSource, "pdf.mjs"), resolve(destination, "pdf.js")),
  copyPdfjsAsset(
    resolve(buildSource, "pdf.worker.mjs"),
    resolve(destination, "pdf.worker.js"),
  ),
  copyFile(
    resolve(webSource, "pdf_viewer.css"),
    resolve(destination, "pdf_viewer.css"),
  ),
  cp(resolve(webSource, "images"), resolve(destination, "images"), {
    recursive: true,
  }),
  copyFile(
    resolve(root, "node_modules/pdfjs-dist/LICENSE"),
    resolve(destination, "LICENSE"),
  ),
]);
console.log(`PDF.js assets copied to ${destination}`);

const bootstrapSource = resolve(root, "node_modules/bootstrap");
const bootstrapDestination = resolve(root, "catalog/static/catalog/vendor/bootstrap");
await mkdir(bootstrapDestination, { recursive: true });
await Promise.all([
  ...[
    "css/bootstrap.min.css",
    "css/bootstrap.min.css.map",
    "js/bootstrap.bundle.min.js",
    "js/bootstrap.bundle.min.js.map",
  ].map((asset) =>
    copyFile(
      resolve(bootstrapSource, "dist", asset),
      resolve(bootstrapDestination, basename(asset)),
    ),
  ),
  copyFile(resolve(bootstrapSource, "LICENSE"), resolve(bootstrapDestination, "LICENSE")),
  // The bundle includes Popper, which retains its own MIT copyright notice.
  copyFile(
    resolve(root, "node_modules/@popperjs/core/LICENSE.md"),
    resolve(bootstrapDestination, "LICENSE-Popper.md"),
  ),
]);
console.log(`Bootstrap assets copied to ${bootstrapDestination}`);
