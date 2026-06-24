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

  const PostSaveReport = async (jsonData, rawData, memberId) => {
    try {
      const response = await axios.post(`${baseURL}/reports`, {
        report: jsonData,
        raw: rawData,
        memberId: memberId
      });
      return response.data;
    } catch (error) {
      console.error("Error saving report:", error);
      throw error;
    }
  };

  const GetReports = async () => {
    try {
      const response = await axios.get(`${baseURL}/reports`);
      return response.data;
    } catch (error) {
      console.error("Error fetching reports:", error);
      throw error;
    }
  };

  return { PostReport, PostSaveReport, GetReports };
}
