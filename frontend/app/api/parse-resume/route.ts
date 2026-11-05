import { NextRequest, NextResponse } from "next/server";
import { createRequire } from "module";

const nodeRequire = createRequire(import.meta.url);
const pdfModule = nodeRequire("pdf-parse");

export async function POST(req: NextRequest) {
  try {
    const formData = await req.formData();
    const file = formData.get("file") as File | null;

    if (!file) {
      return NextResponse.json({ error: "No file uploaded" }, { status: 400 });
    }

    const fileName = file.name || "resume.pdf";
    const extension = fileName.split(".").pop()?.toLowerCase() || "";

    // 1. Text-based files
    if (["txt", "md", "json", "csv"].includes(extension)) {
      const text = await file.text();
      return NextResponse.json({ text, fileName });
    }

    // 2. PDF Parsing via pdf-parse (v2 class or v1 function)
    const buffer = Buffer.from(await file.arrayBuffer());
    let rawText = "";
    let numPages = 1;

    try {
      if (typeof pdfModule === "function") {
        // pdf-parse v1
        const pdfData = await pdfModule(buffer);
        rawText = pdfData.text || "";
        numPages = pdfData.numpages || 1;
      } else if (pdfModule?.PDFParse) {
        // pdf-parse v2
        const parser = new pdfModule.PDFParse({ data: buffer });
        const result = await parser.getText();
        rawText = typeof result === "string" ? result : result.text || "";
        numPages = result.total || 1;
        await parser.destroy();
      } else if (pdfModule?.default && typeof pdfModule.default === "function") {
        const pdfData = await pdfModule.default(buffer);
        rawText = pdfData.text || "";
        numPages = pdfData.numpages || 1;
      }
    } catch (parseErr) {
      console.warn("pdf-parse library parsing error, attempting stream regex fallback:", parseErr);
      // Fallback: extract ASCII string tokens from raw buffer
      const str = buffer.toString("binary");
      const textChunks = str.match(/\(([^()]{3,})\)/g) || [];
      rawText = textChunks.map((s) => s.slice(1, -1)).join(" ");
    }

    // Clean up excessive whitespace
    const cleanText = rawText.replace(/\r\n/g, "\n").trim();

    return NextResponse.json({
      text: cleanText,
      fileName,
      numPages,
    });
  } catch (err: unknown) {
    console.error("Resume parse API error:", err);
    return NextResponse.json(
      { error: "Failed to parse document", details: String(err) },
      { status: 500 }
    );
  }
}
