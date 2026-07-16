import axios from "axios";
import { Document, Packer, Paragraph, TextRun } from "docx";

const baseURL = "http://127.0.0.1:8000";

export default function useExport() {
  const exportDocx = async (returnId) => {
    const response = await axios.get(`${baseURL}/export-report/${returnId}`);

    const doc = new Document({
      sections: [
        {
          children: [
            new Paragraph({
              children: [
                new TextRun({ text: "일일보고서", blob: true, size: 23 }),
              ],
            }),
          ],
        },
      ],
    });

    const blob = await Packer.toBlob(doc);

    return blob;
  };

  return {
    exportDocx,
  };
}
