/**
 * Quartz OFM mermaid init:
 * 1) Resolve CSS calc() colors (mermaid/khroma cannot parse them).
 * 2) High-contrast mindmap palette: light fills + dark text (no purple/navy blobs).
 */
import fs from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"

const ofmDist = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../node_modules/@quartz-community/obsidian-flavored-markdown/dist/index.js",
)

const COLOR_NEEDLE =
  "i[d]=window.getComputedStyle(document.documentElement).getPropertyValue(d)"
const COLOR_REPLACEMENT =
  'i[d]=(function(k){var v=window.getComputedStyle(document.documentElement).getPropertyValue(k).trim();if(k==="--codeFont")return v;var e=document.createElement("span");e.style.color=v;document.documentElement.appendChild(e);var r=getComputedStyle(e).color;e.remove();return r&&r!=="rgba(0, 0, 0, 0)"?r:"#888888"})(d)'

const INIT_NEEDLE =
  'theme:a?"dark":"base",themeVariables:{fontFamily:r["--codeFont"],primaryColor:r["--light"],primaryTextColor:r["--darkgray"],primaryBorderColor:r["--tertiary"],lineColor:r["--darkgray"],secondaryColor:r["--secondary"],tertiaryColor:r["--tertiary"],clusterBkg:r["--light"],edgeLabelBackground:r["--highlight"]}'

const PALETTE_MARK = "cScale0:\"#ffffff\""

const INIT_REPLACEMENT =
  'theme:"base",themeVariables:(function(){var font="Source Sans Pro, Noto Sans SC, Source Han Sans SC, sans-serif";var ink="#1c1917";var css=".mindmap-node text,.nodeLabel,text,tspan{fill:#1c1917!important;color:#1c1917!important;font-weight:600!important}";var pal={fontFamily:font,fontSize:"15px",darkMode:false,background:"#f6f3ec",primaryColor:"#d9efe6",primaryTextColor:ink,primaryBorderColor:ink,lineColor:"#3f3f3f",secondaryColor:"#f5ead3",tertiaryColor:"#e4eaf4",clusterBkg:"#f6f3ec",edgeLabelBackground:"#fff8ee",mainBkg:"#d9efe6",nodeBorder:ink,titleColor:ink,textColor:ink,cScale0:"#ffffff",cScaleLabel0:ink,cScale1:"#c6eadc",cScaleLabel1:ink,cScale2:"#f8d7d2",cScaleLabel2:ink,cScale3:"#d7e2f4",cScaleLabel3:ink,cScale4:"#f5e4c4",cScaleLabel4:ink,cScale5:"#e4dcf4",cScaleLabel5:ink,cScale6:"#dce8c8",cScaleLabel6:ink,cScale7:"#f0e0cc",cScaleLabel7:ink,themeCSS:css};return pal})()'

function replaceBetween(src, startToken, endToken, replacement) {
  const start = src.indexOf(startToken)
  if (start < 0) return null
  const from = src.lastIndexOf("theme:", start)
  if (from < 0) return null
  const end = src.indexOf(endToken, start)
  if (end < 0) return null
  return src.slice(0, from) + replacement + src.slice(end + endToken.length)
}

if (!fs.existsSync(ofmDist)) {
  console.warn("skip mermaid patch: OFM dist not found at", ofmDist)
  process.exit(0)
}

let src = fs.readFileSync(ofmDist, "utf8")
let changed = false

if (src.includes(COLOR_NEEDLE)) {
  src = src.replace(COLOR_NEEDLE, COLOR_REPLACEMENT)
  changed = true
  console.log("applied mermaid CSS color resolver")
}

if (src.includes(INIT_NEEDLE)) {
  src = src.replace(INIT_NEEDLE, INIT_REPLACEMENT)
  changed = true
  console.log("applied mermaid high-contrast palette")
} else if (src.includes(PALETTE_MARK) && src.includes("cScale1:\"#c6eadc\"")) {
  console.log("mermaid high-contrast palette already applied")
} else if (src.includes("themeVariables:(function(dark)") || src.includes("cScale0:\"#2f4a56\"")) {
  const next = replaceBetween(src, "themeVariables:(function", "})(a)", INIT_REPLACEMENT)
  if (next) {
    src = next
    changed = true
    console.log("replaced previous mermaid palette")
  } else {
    console.warn("skip mermaid palette: could not replace previous init")
  }
} else {
  console.warn("skip mermaid palette: initialize snippet not found")
}

if (changed) {
  fs.writeFileSync(ofmDist, src)
}
