import axios from "axios";
import { toRaw } from "vue";
import { Document, Packer, Paragraph, TextRun } from "docx";

const baseURL = "http://127.0.0.1:8000";

export default function useExport() {
  return {
    exportDocx,
  };
}
