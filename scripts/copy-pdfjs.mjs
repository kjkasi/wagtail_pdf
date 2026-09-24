import { copyFile, cp, mkdir } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const buildSource = resolve(root, "node_modules/pdfjs-dist/build");
const webSource = resolve(root, "node_modules/pdfjs-dist/web");
const destination = resolve(root, "catalog/static/catalog/vendor/pdfjs");

await mkdir(destination, { recursive: true });
await Promise.all([
  copyFile(resolve(buildSource, "pdf.mjs"), resolve(destination, "pdf.js")),
  copyFile(
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
