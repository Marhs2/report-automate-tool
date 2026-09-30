import axios from "axios";
import { toRaw } from "vue";
import { selectedUserId } from "./useSelectedUser";
import { sessionToken } from "./useSession";

function apiBaseURL() {
  const fromEnv = import.meta.env.VITE_API_BASE;
  if (fromEnv) return String(fromEnv).replace(/\/$/, "");
  if (import.meta.env.DEV) return "/api";
  if (typeof window !== "undefined") {
    const { protocol, hostname } = window.location;
    if (hostname !== "localhost" && hostname !== "127.0.0.1") {
      return `${protocol}//${hostname}:8000`;
    }
  }
  return "http://127.0.0.1:8000";
}

const baseURL = apiBaseURL();

axios.interceptors.request.use((config) => {
  config.headers = config.headers || {};
  const token = sessionToken.value;
  if (token) config.headers.Authorization = `Bearer ${token}`;
  const id = selectedUserId.value;
  if (id != null && String(id).trim() !== "") {
    config.headers["X-Member-Id"] = String(id);
  }
  return config;
});

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

  /** AI를 돌리지 않고 원문만 보관한다. 고치려고 다시 추출할 필요가 없다. */
  const postReportDraft = async (rawText, reportDate, memberId) => {
    try {
      const response = await axios.post(`${baseURL}/report-drafts`, {
        report: rawText,
        date: reportDate,
        member_id: memberId,
      });
      return response.data;
    } catch (error) {
      console.error("Error saving report draft:", error);
      throw error;
    }
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

  const postCreateWeekly = async (memberId, selects, reportJson) => {
    const response = await axios.post(`${baseURL}/weekly`, {
      member_id: memberId,
      selects: toRaw(selects),
      report_json: reportJson,
    });
    return response.data;
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
    report_id,
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
      if (report_id) {
        payload.report_id = parseInt(report_id, 10);
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

  const postLogin = async (name, password) => {
    const response = await axios.post(`${baseURL}/login`, { name, password });
    return response.data;
  };

  const postLogout = async () => {
    try {
      await axios.post(`${baseURL}/logout`);
    } catch (error) {
      console.error("Error logging out:", error);
    }
  };

  const getMe = async () => {
    const response = await axios.get(`${baseURL}/me`);
    return response.data;
  };

  const changeMyPassword = async (currentPassword, newPassword) => {
    const response = await axios.post(`${baseURL}/me/password`, {
      current_password: currentPassword,
      new_password: newPassword,
    });
    return response.data;
  };

  const setMemberPassword = async (memberId, password) => {
    const response = await axios.post(`${baseURL}/users/${memberId}/password`, {
      password,
    });
    return response.data;
  };

  const postUsers = async (name, teamId, password) => {
    try {
      const payload = { name: name };
      if (teamId != null && teamId !== "") {
        payload.team_id = teamId;
      }
      if (password) payload.password = password;
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


  const getDashboard = async (project = "") => {
    try {
      const response = await axios.get(`${baseURL}/dashboard`, {
        params: project ? { project } : {},
      });
      return response.data;
    } catch (error) {
      console.error("Error fetching dashboard:", error);
      throw error;
    }
  };

  const getWorkRecords = async (kind = "") => {
    try {
      const response = await axios.get(`${baseURL}/work-records`, {
        params: kind ? { kind } : {},
      });
      return response.data;
    } catch (error) {
      console.error("Error fetching work records:", error);
      throw error;
    }
  };

  const getWorkRecord = async (id) => {
    try {
      const response = await axios.get(`${baseURL}/work-records/${id}`);
      return response.data;
    } catch (error) {
      console.error("Error fetching work record:", error);
      throw error;
    }
  };

  const postWorkRecord = async (payload) => {
    try {
      const response = await axios.post(`${baseURL}/work-records`, payload);
      return response.data;
    } catch (error) {
      console.error("Error creating work record:", error);
      throw error;
    }
  };

  const putWorkRecord = async (id, payload) => {
    try {
      const response = await axios.put(`${baseURL}/work-records/${id}`, payload);
      return response.data;
    } catch (error) {
      console.error("Error updating work record:", error);
      throw error;
    }
  };

  const deleteWorkRecord = async (id) => {
    try {
      const response = await axios.delete(`${baseURL}/work-records/${id}`);
      return response.data;
    } catch (error) {
      console.error("Error deleting work record:", error);
      throw error;
    }
  };

  /**
   * 녹음 조각 하나를 받아 적는다. 백엔드가 사내 음성 인식 서버(R2T2)로 넘긴다.
   * polish면 이름 · 용어 · 약어 · 숫자 오타를 사내 용어로 교정한다(녹취록용 긴 조각에만).
   */
  const transcribeMeetingAudio = async (blob, { polish = false, session = "", filename = "meeting.wav" } = {}) => {
    const formData = new FormData();
    formData.append("file", blob, filename);
    formData.append("polish", polish ? "true" : "false");
    if (session) formData.append("session", session);
    const response = await axios.post(`${baseURL}/meeting/transcribe`, formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return response.data;
  };

  /** 녹음 세션을 연다. 녹취록용 조각을 쌓아 두었다가 정지하면 회의 전체로 말한 사람을 나눈다. */
  const createMeetingSession = async () => {
    const response = await axios.post(`${baseURL}/meeting/sessions`);
    return response.data;
  };

  /** 세션 전체를 말한 사람별로 나눠 받아 적는다. 한 시간짜리면 몇 분 걸린다. */
  const diarizeMeetingSession = async (sessionId, numSpeakers = null) => {
    const response = await axios.post(`${baseURL}/meeting/sessions/${sessionId}/diarize`, {
      numSpeakers,
    });
    return response.data;
  };

  const deleteMeetingSession = async (sessionId) => {
    const response = await axios.delete(`${baseURL}/meeting/sessions/${sessionId}`);
    return response.data;
  };

  /** 녹취록을 회의록 칸(제목 · 안건 · 결정 · 후속 할 일)으로 요약한다. */
  const summarizeMeeting = async (transcript, meetingDate) => {
    const response = await axios.post(`${baseURL}/meeting/summarize`, {
      transcript,
      meetingDate,
    });
    return response.data;
  };

  return {
    postReport,
    postReportPptx,
    getReportDraft,
    postReportDraft,
    postSaveReport,
    getReports,
    getReportById,
    getUserActivities,
    getHolidays,
    postWeeklyReport,
    postCreateWeekly,
    getWeeklyReport,
    getWeeklyReportById,
    downloadWeeklyPptx,
    updateWeeklyReport,
    postLogin,
    postLogout,
    getMe,
    changeMyPassword,
    setMemberPassword,
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
    getDashboard,
    getWorkRecords,
    getWorkRecord,
    postWorkRecord,
    putWorkRecord,
    deleteWorkRecord,
    transcribeMeetingAudio,
    createMeetingSession,
    diarizeMeetingSession,
    deleteMeetingSession,
    summarizeMeeting,
  };
}
