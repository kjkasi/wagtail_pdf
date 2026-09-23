import { copyFile, mkdir } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const source = resolve(root, "node_modules/pdfjs-dist/build");
const destination = resolve(root, "catalog/static/catalog/vendor/pdfjs");

await mkdir(destination, { recursive: true });
await Promise.all([
  copyFile(resolve(source, "pdf.mjs"), resolve(destination, "pdf.js")),
  copyFile(
    resolve(source, "pdf.worker.mjs"),
    resolve(destination, "pdf.worker.js"),
  ),
  copyFile(
    resolve(root, "node_modules/pdfjs-dist/LICENSE"),
    resolve(destination, "LICENSE"),
  ),
]);
console.log(`PDF.js assets copied to ${destination}`);
