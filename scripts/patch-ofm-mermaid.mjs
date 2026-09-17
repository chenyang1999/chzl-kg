/**
 * Quartz OFM passes CSS custom properties into mermaid.initialize().
 * Obsidian/quartz-themes stores --tertiary as hsl(calc(...)), which
 * mermaid 11 / khroma cannot parse, so diagrams never render.
 *
 * Resolve color vars through the browser's CSS engine (dummy element)
 * before handing them to mermaid.
 */
import fs from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"

const ofmDist = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../node_modules/@quartz-community/obsidian-flavored-markdown/dist/index.js",
)

const NEEDLE =
  "i[d]=window.getComputedStyle(document.documentElement).getPropertyValue(d)"
const REPLACEMENT =
  'i[d]=(function(k){var v=window.getComputedStyle(document.documentElement).getPropertyValue(k).trim();if(k==="--codeFont")return v;var e=document.createElement("span");e.style.color=v;document.documentElement.appendChild(e);var r=getComputedStyle(e).color;e.remove();return r&&r!=="rgba(0, 0, 0, 0)"?r:"#888888"})(d)'

if (!fs.existsSync(ofmDist)) {
  console.warn("skip mermaid patch: OFM dist not found at", ofmDist)
  process.exit(0)
}

const src = fs.readFileSync(ofmDist, "utf8")
if (src.includes("dummy element") || src.includes('k==="--codeFont"')) {
  console.log("mermaid color patch already applied")
  process.exit(0)
}
if (!src.includes(NEEDLE)) {
  console.warn("skip mermaid patch: expected OFM mermaid init snippet not found")
  process.exit(0)
}

fs.writeFileSync(ofmDist, src.replace(NEEDLE, REPLACEMENT))
console.log("patched OFM mermaid themeVariables to resolve CSS calc() colors")
