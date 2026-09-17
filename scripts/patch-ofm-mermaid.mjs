/**
 * Quartz OFM mermaid init:
 * 1) Resolve CSS calc() colors (mermaid/khroma cannot parse them).
 * 2) Replace the purple/white themeVariables with a paper + sage palette.
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

const INIT_REPLACEMENT =
  'theme:"base",themeVariables:(function(dark){var font="Source Sans Pro, Noto Sans SC, Source Han Sans SC, sans-serif";var light={fontFamily:font,fontSize:"15px",primaryColor:"#d8e4df",primaryTextColor:"#2c3338",primaryBorderColor:"#5f7d76",lineColor:"#7a8a84",secondaryColor:"#eadcc8",tertiaryColor:"#cfd8e3",clusterBkg:"#f4f1ea",edgeLabelBackground:"#efeae2",background:"#f4f1ea",mainBkg:"#d8e4df",nodeBorder:"#5f7d76",titleColor:"#2c3338",cScale0:"#2f4a56",cScaleLabel0:"#f4f1ea",cScale1:"#d8e4df",cScaleLabel1:"#2c3338",cScale2:"#eadcc8",cScaleLabel2:"#3a3228",cScale3:"#cfd8e3",cScaleLabel3:"#2c3338",cScale4:"#e4d0d0",cScaleLabel4:"#3a2c2c",cScale5:"#d5dcc8",cScaleLabel5:"#2c3338",cScale6:"#d8cfc4",cScaleLabel6:"#2c3338",cScale7:"#c9dce3",cScaleLabel7:"#2c3338"};var night={fontFamily:font,fontSize:"15px",primaryColor:"#3d524c",primaryTextColor:"#e8e4dc",primaryBorderColor:"#8fb4aa",lineColor:"#9aa8a2",secondaryColor:"#5a4e40",tertiaryColor:"#3a4550",clusterBkg:"#1c1e20",edgeLabelBackground:"#2a2c2e",background:"#1c1e20",mainBkg:"#3d524c",nodeBorder:"#8fb4aa",titleColor:"#e8e4dc",cScale0:"#8fb4aa",cScaleLabel0:"#1c1e20",cScale1:"#3d524c",cScaleLabel1:"#e8e4dc",cScale2:"#5a4e40",cScaleLabel2:"#e8e4dc",cScale3:"#3a4550",cScaleLabel3:"#e8e4dc",cScale4:"#534040",cScaleLabel4:"#e8e4dc",cScale5:"#44503a",cScaleLabel5:"#e8e4dc",cScale6:"#4a433c",cScaleLabel6:"#e8e4dc",cScale7:"#3a4e54",cScaleLabel7:"#e8e4dc"};return dark?night:light})(a)'

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
  console.log("applied mermaid paper/sage palette")
} else if (src.includes("cScale0:\"#2f4a56\"")) {
  console.log("mermaid palette already applied")
} else {
  console.warn("skip mermaid palette: initialize snippet not found")
}

if (changed) {
  fs.writeFileSync(ofmDist, src)
}
