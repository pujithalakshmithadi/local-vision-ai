
const pptxgen = require("pptxgenjs");
const fs = require("fs");
const path = require("path");

async function main() {
  const inputPath = process.argv[2];
  const outputPath = process.argv[3];

  if (!inputPath || !outputPath) {
    throw new Error("Input JSON and output PPTX paths are required.");
  }

  const data = JSON.parse(fs.readFileSync(inputPath, "utf8"));

  if (!Array.isArray(data.slides) || data.slides.length === 0) {
    throw new Error("No slides were provided.");
  }

  const pptx = new pptxgen();

  pptx.layout = "LAYOUT_WIDE";
  pptx.author = "Local Vision AI";
  pptx.subject = "AI-generated presentation";
  pptx.title = data.presentation_title || "AI Presentation";
  pptx.company = "Local Vision AI";

  pptx.theme = {
    headFontFace: "Aptos Display",
    bodyFontFace: "Aptos",
    lang: "en-US"
  };

  pptx.defineSlideMaster({
    title: "MASTER",
    background: { color: "F8FAFC" },
    objects: [
      {
        rect: {
          x: 0,
          y: 0,
          w: 0.16,
          h: 7.5,
          line: { color: "2563EB", transparency: 100 },
          fill: { color: "2563EB" }
        }
      },
      {
        line: {
          x: 0.55,
          y: 6.95,
          w: 12.1,
          h: 0,
          line: { color: "CBD5E1", width: 1 }
        }
      },
      {
        text: {
          text: "LOCAL VISION AI",
          options: {
            x: 0.6,
            y: 7.05,
            w: 4,
            h: 0.2,
            fontFace: "Aptos",
            fontSize: 9,
            color: "64748B",
            margin: 0
          }
        }
      }
    ],
    slideNumber: {
      x: 12.1,
      y: 7.04,
      w: 0.5,
      h: 0.22,
      color: "64748B",
      fontFace: "Aptos",
      fontSize: 9,
      align: "right"
    }
  });

  for (const item of data.slides) {
    const slide = pptx.addSlide("MASTER");

    slide.addText(item.title || "Untitled Slide", {
      x: 0.75,
      y: 0.55,
      w: 11.8,
      h: 0.8,
      fontFace: "Aptos Display",
      fontSize: 28,
      bold: true,
      color: "172554",
      margin: 0.05,
      breakLine: false,
      fit: "shrink"
    });

    const bullets = Array.isArray(item.bullets) ? item.bullets : [];

    if (bullets.length > 0) {
      const bulletRuns = [];

      bullets.forEach((text) => {
        bulletRuns.push({
          text: String(text),
          options: {
            bullet: { indent: 20 },
            hanging: 4,
            breakLine: true
          }
        });
      });

      slide.addText(bulletRuns, {
        x: 0.95,
        y: 1.65,
        w: 11.2,
        h: 4.8,
        fontFace: "Aptos",
        fontSize: 20,
        color: "334155",
        breakLine: false,
        paraSpaceAfterPt: 18,
        valign: "mid",
        margin: 0.08,
        fit: "shrink"
      });
    }

    if (item.speaker_notes && typeof slide.addNotes === "function") {
      slide.addNotes(item.speaker_notes);
    }
  }

  await pptx.writeFile({ fileName: outputPath });

  console.log("PowerPoint created:", outputPath);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
