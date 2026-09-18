import axios from "axios";
import { toRaw } from "vue";

const baseURL = "http://127.0.0.1:8000";

export default function useApi() {
  const postReport = async (reportData, dateData, memberId) => {
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

  const postReportPptx = async (file, dateData, memberId) => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("date", dateData);
    formData.append("member_id", String(memberId));
    try {
      const response = await axios.post(
        `${baseURL}/send-report-pptx`,
        formData,
        {
          headers: { "Content-Type": "multipart/form-data" },
        },
      );
      return response.data;
    } catch (error) {
      console.error("Error sending PPTX report:", error);
      throw error;
    }
  };

  const deleteReport = async (reportId) => {
    try {
      await axios.delete(`${baseURL}/reports/${reportId}`);
    } catch (error) {
      console.error("Error deleting report:", error);
      throw error;
    }
  };

  const deleteWeeklyReport = async (reportId) => {
    try {
      await axios.delete(`${baseURL}/weekly/${reportId}`);
    } catch (error) {
      console.error("Error deleting weekly report:", error);
      throw error;
    }
  };

  const getReportDraft = async (memberId, reportDate) => {
    const response = await axios.get(
      `${baseURL}/report-drafts/${memberId}/${reportDate}`,
    );
    return response.data;
  };

  const postWeeklyReport = async (userId, selects) => {
    const response = await axios.post(`${baseURL}/weekly-report`, {
      userId,
      selects: toRaw(selects),
    });

    return response;
  };

  const getWeeklyReport = async (userId) => {
    try {
      const response = await axios.get(`${baseURL}/weekly/${userId}`);
      return response.data;
    } catch (error) {
      console.error("Error fetching weekly report:", error);
      throw error;
    }
  };

  const getWeeklyReportById = async (weeklyId) => {
    try {
      const response = await axios.get(`${baseURL}/weeklyById/${weeklyId}`);
      return response.data;
    } catch (error) {
      console.error("Error fetching weekly report by id:", error);
      throw error;
    }
  };

  const downloadWeeklyPptx = async (weeklyId) => {
    try {
      const response = await axios.get(
        `${baseURL}/weeklyById/${weeklyId}/pptx`,
        { responseType: "blob" },
      );
      return response.data;
    } catch (error) {
      console.error("Error downloading weekly pptx:", error);
      throw error;
    }
  };

  const updateWeeklyReport = async (weeklyId, reportJson) => {
    try {
      const response = await axios.put(`${baseURL}/weekly/${weeklyId}`, {
        report_json: reportJson,
      });
      return response.data;
    } catch (error) {
      console.error("Error updating weekly report:", error);
      throw error;
    }
  };

  const getHolidays = async (year) => {
    try {
      const response = await axios.get(`${baseURL}/holidays`, {
        params: { year },
      });
      return response.data;
    } catch (error) {
      console.error("Error fetching holidays:", error);
      return [];
    }
  };

  const getUserActivities = async (year, month, startDate, endDate) => {
    try {
      const response = await axios.get(`${baseURL}/user-activities`, {
        params: {
          year,
          month,
          ...(startDate && endDate
            ? { start_date: startDate, end_date: endDate }
            : {}),
        },
      });
      return response.data;
    } catch (error) {
      console.error("Error fetching user activities:", error);
      throw error;
    }
  };

  const postSaveReport = async (
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

  const getReports = async () => {
    try {
      const response = await axios.get(`${baseURL}/reports`);
      return response.data;
    } catch (error) {
      console.error("Error fetching reports:", error);
      throw error;
    }
  };

  const getReportById = async (reportId) => {
    try {
      const response = await axios.get(`${baseURL}/reports/${reportId}`);
      return response.data;
    } catch (error) {
      console.error("Error fetching report by id:", error);
      throw error;
    }
  };

  const postUsers = async (name, teamId) => {
    try {
      const payload = { name: name };
      if (teamId != null && teamId !== "") {
        payload.team_id = teamId;
      }
      const response = await axios.post(`${baseURL}/users`, payload);
      return response.data;
    } catch (error) {
      console.error("Error creating user:", error);
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

  const postTeams = async (name) => {
    try {
      const response = await axios.post(`${baseURL}/teams`, {
        team_name: name,
      });
      return response.data;
    } catch (error) {
      console.error("Error creating team:", error);
      throw error;
    }
  };

  const setTeam = async (teamId, userId) => {
    try {
      const response = await axios.post(`${baseURL}/teams/set`, {
        team_id: teamId,
        user_id: userId,
      });
      return response.data;
    } catch (error) {
      console.error("Error setting team:", error);
      throw error;
    }
  };

  const getTeams = async () => {
    try {
      const response = await axios.get(`${baseURL}/teams`);
      return response.data;
    } catch (error) {
      console.error("Error fetching teams:", error);
      throw error;
    }
  };

  const getTeamByMemberId = async (memberId) => {
    try {
      const response = await axios.get(`${baseURL}/teams/${memberId}`);
      return response.data;
    } catch (error) {
      console.error("Error fetching team by member id:", error);
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

  const getRegisteredProjectNames = async () => {
    try {
      const response = await axios.get(`${baseURL}/project-names/registered`);
      return response.data;
    } catch (error) {
      console.error("Error fetching registered project names:", error);
      throw error;
    }
  };

  const postProjectName = async (name, keywords = "") => {
    try {
      const response = await axios.post(`${baseURL}/project-names`, { name, keywords });
      return response.data;
    } catch (error) {
      console.error("Error creating project name:", error);
      throw error;
    }
  };

  const deleteProjectName = async (projectName) => {
    try {
      const response = await axios.delete(
        `${baseURL}/project-names/${encodeURIComponent(projectName)}`,
      );
      return response.data;
    } catch (error) {
      console.error("Error deleting project name:", error);
      throw error;
    }
  };

  const updateProjectNameKeywords = async (projectName, keywords) => {
    try {
      const response = await axios.put(
        `${baseURL}/project-names/${encodeURIComponent(projectName)}`,
        { keywords },
      );
      return response.data;
    } catch (error) {
      console.error("Error updating project name keywords:", error);
      throw error;
    }
  };

  const recommendKeywords = async (report) => {
    try {
      const response = await axios.post(
        `${baseURL}/project-names/recommend`,
        { report },
        { timeout: 180000 },
      );
      return response.data;
    } catch (error) {
      console.error("Error recommending keywords:", error);
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
    postReport,
    postReportPptx,
    getReportDraft,
    postSaveReport,
    getReports,
    getReportById,
    getUserActivities,
    getHolidays,
    postWeeklyReport,
    getWeeklyReport,
    getWeeklyReportById,
    downloadWeeklyPptx,
    updateWeeklyReport,
    postUsers,
    getUsers,
    postTeams,
    getTeams,
    getProjectNames,
    getRegisteredProjectNames,
    postProjectName,
    deleteProjectName,
    updateProjectNameKeywords,
    recommendKeywords,
    getProjectTimeline,
    deleteWeeklyReport,
    deleteReport,
    getTeamByMemberId,
    setTeam,
  };
}
