/**
 * 화면에 보일 오류 한 줄. 무슨 일이 났고 무엇을 하면 되는지 한국어로만 말한다.
 * 백엔드가 준 detail은 이미 한국어라 그대로 쓰고, 브라우저 · 네트워크 오류("Network Error" 등)는 바꿔 말한다.
 */
export function errorMessage(error, fallback = "처리하지 못했습니다. 잠시 뒤 다시 시도해 주세요.") {
    const response = error?.response;
    const detail = response?.data?.detail;
    if (typeof detail === "string" && detail.trim()) return detail.trim();
    if (error?.code === "ECONNABORTED" || error?.code === "ETIMEDOUT") {
        return "응답이 너무 오래 걸립니다. 잠시 뒤 다시 시도해 주세요.";
    }
    if (!response && (error?.request || error?.code === "ERR_NETWORK" || error?.message === "Network Error")) {
        return "서버에 연결하지 못했습니다. 사내망 연결을 확인하고 다시 시도해 주세요.";
    }
    const status = Number(response?.status);
    if (status === 401) return "로그인이 풀렸습니다. 다시 로그인해 주세요.";
    if (status === 403) return "이 작업을 할 권한이 없습니다.";
    if (status >= 500) return "서버에서 문제가 생겼습니다. 잠시 뒤 다시 시도해 주세요.";
    return fallback;
}
