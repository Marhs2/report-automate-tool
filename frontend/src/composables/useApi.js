import axios from "axios";
import { toRaw } from "vue";

const baseURL = "http://127.0.0.1:8000";

export default function useAPI() {
  const PostReport = async (reportData, dateData, memberId) => {
    try {
      const response = await axios.post(`${baseURL}/send-report`, {
        report: reportData.content,
        date: dateData,
        member_id: memberId,
      });
      return response.data;
    } catch (error) {
      console.error("Error sending report:", error);
      throw error;
    }
  };

  const postWeekly = async (userId, selects) => {
    const response = await axios.post(`${baseURL}/weekly-report`, {
      userId,
      selects: toRaw(selects),
    });

    return response;
  };

  const GetWeeklyReport = async () => {
    try {
      const response = await axios.get(`${baseURL}/weekly`);
      return response.data;
    } catch (error) {
      console.error("Error fetching weekly report:", error);
      throw error;
    }
  };

  const GetWeeklyReportById = async (weeklyId) => {
    try {
      const response = await axios.get(`${baseURL}/weeklyById/${weeklyId}`);
      console.log(response.data);
      return response.data;
    } catch (error) {
      console.error("Error fetching weekly report by id:", error);
      throw error;
    }
  };

  const GetUserActivities = async (year, month) => {
    try {
      const response = await axios.get(`${baseURL}/user-activities`, {
        params: { year, month },
      });
      return response.data;
    } catch (error) {
      console.error("Error fetching user activities:", error);
      throw error;
    }
  };

  const PostSaveReport = async (
    parsed_json,
    rawData,
    member_id,
    report_date,
  ) => {
    try {
      const payload = {
        report: rawData,
        parsed_json: parsed_json,
        member_id: parseInt(member_id),
      };
      if (report_date) {
        payload.report_date = report_date;
      }
      const response = await axios.post(`${baseURL}/reports`, payload);
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

  const GetReportById = async (reportId) => {
    try {
      const response = await axios.get(`${baseURL}/reports/${reportId}`);
      return response.data;
    } catch (error) {
      console.error("Error fetching report by id:", error);
      throw error;
    }
  };

  const GetProjects = async () => {
    try {
      const response = await axios.get(`${baseURL}/projects`);
      return response.data;
    } catch (error) {
      console.error("Error fetching projects:", error);
      throw error;
    }
  };

  const postUsers = async (name) => {
    try {
      const response = await axios.post(`${baseURL}/users`, {
        name: name,
      });
      return response.data;
    } catch (error) {
      console.error("Error fetching users:", error);
      throw error;
    }
  };

  const getUsers = async () => {
    try {
      const response = await axios.get(`${baseURL}/users`);
      return response.data;
    } catch (error) {
      console.error("Error fetching users:", error);
      throw error;
    }
  };

  const getProjectAliases = async () => {
    try {
      const response = await axios.get(`${baseURL}/project-aliases`);
      return response.data;
    } catch (error) {
      console.error("Error fetching project aliases:", error);
      throw error;
    }
  };

  const postProjectAlias = async (alias_name, canonical_name) => {
    try {
      const response = await axios.post(`${baseURL}/project-aliases`, {
        alias_name,
        canonical_name,
      });
      return response.data;
    } catch (error) {
      console.error("Error creating project alias:", error);
      throw error;
    }
  };

  const deleteProjectAlias = async (aliasId) => {
    try {
      const response = await axios.delete(
        `${baseURL}/project-aliases/${aliasId}`,
      );
      return response.data;
    } catch (error) {
      console.error("Error deleting project alias:", error);
      throw error;
    }
  };

  const getProjectNames = async () => {
    try {
      const response = await axios.get(`${baseURL}/project-names`);
      return response.data;
    } catch (error) {
      console.error("Error fetching project names:", error);
      throw error;
    }
  };

  const getProjectTimeline = async (name, memberId) => {
    try {
      const params = { name };
      if (memberId) params.member_id = memberId;
      const response = await axios.get(`${baseURL}/project-timeline`, {
        params,
      });
      return response.data;
    } catch (error) {
      console.error("Error fetching project timeline:", error);
      throw error;
    }
  };

  return {
    PostReport,
    PostSaveReport,
    GetReports,
    GetReportById,
    GetProjects,
    GetUserActivities,
    postWeekly,
    GetWeeklyReport,
    GetWeeklyReportById,
    postUsers,
    getUsers,
    getProjectAliases,
    postProjectAlias,
    deleteProjectAlias,
    getProjectNames,
    getProjectTimeline,
  };
}
