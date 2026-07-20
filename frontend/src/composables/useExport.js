import axios from "axios";
import { toRaw } from "vue";

const baseURL = "http://127.0.0.1:8000";

export default function useExport() {
  const exportDocx = async (userId, selects) => {
    const response = await axios.post(`${baseURL}/weekly-report`, {
      userId,
      selects: toRaw(selects),
    });

    return response;
  };

  return {
    exportDocx,
  };
}
