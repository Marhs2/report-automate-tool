import axios from "axios";

const baseURL = "http://127.0.0.1:8000";

export default function useAPI() {
  const PostReport = async (reportData) => {
    const replacedData = reportData.content.replace(/\n/g, "<br>");

    try {
      const response = await axios.post(`${baseURL}/send-report`, {
        report: replacedData,
      });
      return response.data;
    } catch (error) {
      console.error("Error sending report:", error);
      throw error;
    }
  };

  return { PostReport };
}
