
let extractedPage = null;
let analyzedData = null;

const API_BASE = "http://127.0.0.1:8000";

const status = document.getElementById("status");
const result = document.getElementById("result");

function setStatus(message) {
  status.textContent = message;
}

function showError(prefix, error) {
  console.error(prefix, error);
  setStatus(prefix + ": " + (error?.message || String(error)));
}

function pageText(page) {
  return [
    "Page title: " + page.title,
    "URL: " + page.url,
    "Headings:\n" + (page.headings || []).join("\n"),
    "Paragraphs:\n" + (page.paragraphs || []).join("\n"),
    "Tables:\n" + JSON.stringify(page.tables || []),
    "Image descriptions:\n" + JSON.stringify(
      (page.images || []).map(img => ({
        alt: img.alt,
        width: img.width,
        height: img.height
      }))
    ),
    "SVG count: " + page.svgCount,
    "Canvas count: " + page.canvasCount
  ].join("\n\n").slice(0, 24000);
}

async function postJSON(endpoint, body) {
  let response;

  try {
    response = await fetch(API_BASE + endpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Accept": "application/json"
      },
      body: JSON.stringify(body)
    });
  } catch (error) {
    throw new Error(
      "Cannot connect to backend at " + API_BASE +
      ". Check that FastAPI is running. Details: " +
      (error.message || error)
    );
  }

  const responseText = await response.text();

  let data;

  try {
    data = responseText ? JSON.parse(responseText) : null;
  } catch {
    throw new Error(
      "Backend returned invalid JSON. HTTP " +
      response.status + ". Response: " +
      responseText.slice(0, 500)
    );
  }

  if (!response.ok) {
    throw new Error(
      "Backend error " + response.status + ": " +
      JSON.stringify(data)
    );
  }

  return data;
}

// Read the current webpage
document.getElementById("readPage").addEventListener(
  "click",
  async () => {
    setStatus("Reading webpage...");
    result.textContent = "";
    extractedPage = null;
    analyzedData = null;

    try {
      const [tab] = await chrome.tabs.query({
        active: true,
        currentWindow: true
      });

      if (!tab?.id || !tab.url?.startsWith("http")) {
        throw new Error(
          "Open a normal website first, then try again."
        );
      }

      const response = await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        func: () => {
          const clean = text =>
            (text || "").replace(/\s+/g, " ").trim();

          return {
            title: document.title,
            url: location.href,

            headings: Array.from(
              document.querySelectorAll(
                "h1,h2,h3,h4,h5,h6"
              )
            )
              .map(el => clean(el.innerText))
              .filter(Boolean),

            paragraphs: Array.from(
              document.querySelectorAll("p")
            )
              .map(el => clean(el.innerText))
              .filter(Boolean),

            tables: Array.from(
              document.querySelectorAll("table")
            ).map(table =>
              Array.from(table.querySelectorAll("tr"))
                .map(row =>
                  Array.from(
                    row.querySelectorAll("th,td")
                  ).map(cell => clean(cell.innerText))
                )
            ),

            images: Array.from(document.images).map(img => ({
              alt: clean(img.alt),
              src: img.currentSrc || img.src || "",
              width: img.naturalWidth,
              height: img.naturalHeight
            })),

            svgCount: document.querySelectorAll("svg").length,
            canvasCount: document.querySelectorAll("canvas").length
          };
        }
      });

      extractedPage = response[0]?.result;

      if (!extractedPage) {
        throw new Error("Could not read this webpage.");
      }

      setStatus("Page read successfully!");

      result.textContent = [
        "Title: " + extractedPage.title,
        "URL: " + extractedPage.url,
        "Headings: " + extractedPage.headings.length,
        "Paragraphs: " + extractedPage.paragraphs.length,
        "Tables: " + extractedPage.tables.length,
        "Images: " + extractedPage.images.length,
        "",
        "Next: Click Analyze Webpage to run AI analysis."
      ].join("\n");

    } catch (error) {
      showError("Page reading failed", error);
    }
  }
);

// Analyze the webpage with AI
document.getElementById("sendAI").addEventListener(
  "click",
  async () => {
    if (!extractedPage) {
      setStatus("First click Read This Page.");
      return;
    }

    setStatus("Connecting to AI backend...");
    result.textContent = "";

    try {
      analyzedData = await postJSON("/analyze", {
        text: pageText(extractedPage)
      });

      setStatus("AI analysis completed!");

      result.textContent = JSON.stringify(
        analyzedData,
        null,
        2
      );

    } catch (error) {
      showError("Analysis failed", error);
    }
  }
);

// Ask a question about the webpage
document.getElementById("askAI").addEventListener(
  "click",
  async () => {
    if (!extractedPage) {
      setStatus("First click Read This Page.");
      return;
    }

    const questionElement =
      document.getElementById("question");

    const question = questionElement.value.trim();

    if (!question) {
      setStatus("Type a question first.");
      questionElement.focus();
      return;
    }

    setStatus("Sending question to AI...");
    result.textContent = "";

    try {
      const data = await postJSON("/ask", {
        text: pageText(extractedPage),
        question: question
      });

      setStatus("Answer received!");

      result.textContent = JSON.stringify(
        data,
        null,
        2
      );

    } catch (error) {
      showError("Question failed", error);
    }
  }
);

// Generate and download a PowerPoint presentation
document.getElementById("makePPT").addEventListener(
  "click",
  async () => {
    if (!extractedPage) {
      setStatus("First click Read This Page.");
      return;
    }

    setStatus("Generating slides...");
    result.textContent = "";

    let downloadUrl = null;

    try {
      const slidesData = await postJSON(
        "/generate-slides",
        { text: pageText(extractedPage) }
      );

      setStatus("Creating PowerPoint file...");

      const pptResponse = await fetch(
        API_BASE + "/create-pptx",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Accept":
              "application/vnd.openxmlformats-officedocument.presentationml.presentation"
          },
          body: JSON.stringify(slidesData)
        }
      );

      if (!pptResponse.ok) {
        const errorText = await pptResponse.text();

        throw new Error(
          "PPT creation failed: HTTP " +
          pptResponse.status + ". " +
          errorText.slice(0, 500)
        );
      }

      const blob = await pptResponse.blob();

      if (!blob.size) {
        throw new Error("Backend returned an empty PPT file.");
      }

      downloadUrl = URL.createObjectURL(blob);

      const link = document.createElement("a");
      link.href = downloadUrl;
      link.download = "Local-Vision-AI.pptx";

      document.body.appendChild(link);
      link.click();
      link.remove();

      setStatus("PowerPoint download started!");

      result.textContent =
        "Presentation: " +
        (slidesData.presentation_title || "Webpage summary") +
        "\nSlides: " +
        (slidesData.slides?.length || 0) +
        "\nFile size: " +
        Math.round(blob.size / 1024) + " KB";

    } catch (error) {
      showError("PPT generation failed", error);

    } finally {
      if (downloadUrl) {
        setTimeout(
          () => URL.revokeObjectURL(downloadUrl),
          10000
        );
      }
    }
  }
);
