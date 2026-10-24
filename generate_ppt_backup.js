
const pptxgen = require("pptxgenjs");

const pptx = new pptxgen();

pptx.layout = "LAYOUT_WIDE";
pptx.author = "Local Vision AI";
pptx.subject = "Generated from webpage content";
pptx.title = "Solar Energy";
pptx.company = "Local Vision AI";
pptx.lang = "en-US";

pptx.theme = {
  headFontFace: "Aptos Display",
  bodyFontFace: "Aptos",
  lang: "en-US",
};

const slides = [
  {
    title: "Solar Energy",
    points: [
      "Introduction to solar energy",
      "How sunlight can be converted into electricity",
      "Benefits and practical limitations",
    ],
  },
  {
    title: "How Solar Energy Works",
    points: [
      "Solar panels capture sunlight",
      "Photovoltaic cells convert light into electrical energy",
      "An inverter converts electricity into a usable form",
    ],
  },
  {
    title: "Key Benefits",
    points: [
      "Renewable source of energy",
      "Can reduce dependence on fossil fuels",
      "Produces no direct greenhouse gas emissions during operation",
    ],
  },
  {
    title: "Challenges",
    points: [
      "Electricity production depends on sunlight",
      "Installation can have an upfront cost",
      "Energy storage may be needed for use at night",
    ],
  },
  {
    title: "Conclusion",
    points: [
      "Solar energy is an important renewable energy option",
      "Its suitability depends on location, cost, and energy needs",
      "Good system design helps improve its usefulness",
    ],
  },
];

slides.forEach((item, index) => {
  const slide = pptx.addSlide();

  slide.background = { color: "F7F9FC" };

  slide.addText(item.title, {
    x: 0.7,
    y: 0.55,
    w: 11.8,
    h: 0.8,
    fontFace: "Aptos Display",
    fontSize: 30,
    bold: true,
    color: "17365D",
    margin: 0.05,
    breakLine: false,
  });

  slide.addShape(pptx.ShapeType.line, {
    x: 0.75,
    y: 1.5,
    w: 11.7,
    h: 0,
    line: { color: "2F75B5", width: 2 },
  });

  slide.addText(
    item.points.map((point) => ({
      text: point,
      options: {
        bullet: { indent: 20 },
        hanging: 4,
        breakLine: true,
        paraSpaceAfterPt: 18,
      },
    })),
    {
      x: 1.0,
      y: 1.95,
      w: 10.8,
      h: 4.3,
      fontFace: "Aptos",
      fontSize: 22,
      color: "263238",
      valign: "mid",
      margin: 0.15,
      breakLine: false,
      paraSpaceAfterPt: 18,
    }
  );

  slide.addText(`Local Vision AI  |  ${index + 1} / ${slides.length}`, {
    x: 8.5,
    y: 7.05,
    w: 4.0,
    h: 0.2,
    fontSize: 10,
    color: "64748B",
    align: "right",
    margin: 0,
  });
});

pptx.writeFile({ fileName: "solar_energy_demo.pptx" })
  .then(() => {
    console.log("Success! solar_energy_demo.pptx created.");
  })
  .catch((error) => {
    console.error("PowerPoint generation failed:", error);
    process.exitCode = 1;
  });
