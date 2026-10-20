<script setup>
import { ref } from "vue";
import { useRouter } from "vue-router";
import useApi from "../composables/useApi";
import { isAdmin, leaderTeamId, sessionToken } from "../composables/useSession";
import { selectedUserId } from "../composables/useSelectedUser";
import { selectedTeamId } from "../composables/useSelectedTeam";
import { useDialog } from "../composables/useDialog";

const router = useRouter();
const { postLogin } = useApi();
const { alert: showAlert } = useDialog();

const name = ref("");
const password = ref("");
const isSaving = ref(false);

const login = async () => {
    const userName = name.value.trim();
    const secret = password.value;
    if (!userName) {
        showAlert("이름을 입력해주세요.");
        return;
    }
    if (!secret) {
        showAlert("비밀번호를 입력해주세요.");
        return;
    }
    isSaving.value = true;
    try {
        const data = await postLogin(userName, secret);
        sessionToken.value = data.token;
        isAdmin.value = Boolean(data.is_admin);
        leaderTeamId.value = data.leads_team_id ?? null;
        selectedUserId.value = data.member_id;
        selectedTeamId.value = data.team_id ?? null;
        router.replace("/");
    } catch (error) {
        const detail = error?.response?.data?.detail;
        showAlert(
            typeof detail === "string" && detail.trim()
                ? detail
                : "로그인에 실패했습니다.",
        );
    } finally {
        isSaving.value = false;
    }
};
</script>

<template>
    <div class="login-page">
        <aside class="login-side" aria-hidden="true">
            <p class="login-brand">일일보고</p>
            <p class="login-lead">
                오늘 한 일을 붙여 넣으면 프로젝트별로 나누고,<br />
                한 주가 끝나면 주간보고 초안까지 만들어요.
            </p>
            <div class="login-sample">
                <p class="login-sample-head">
                    <span>대한전선 IoT</span>
                    <span class="state-chip is-success">저장됨</span>
                </p>
                <p><span class="cat-tag is-done">완료</span>현장 실측 체크리스트 확정</p>
                <p><span class="cat-tag is-progress">진행</span>2층 좌표 잔여 4곳 확인 중</p>
                <p><span class="cat-tag is-issue">이슈</span>최신 도면 수령 지연</p>
                <p><span class="cat-tag is-next">다음</span>관제 메뉴 시안 수정</p>
            </div>
        </aside>

        <main class="login-main">
            <form class="login-form" @submit.prevent="login">
                <h1 class="t-title">로그인</h1>
                <p class="t-desc">사내에서 쓰는 이름과 비밀번호를 입력하세요.</p>
                <label class="login-field">
                    <span>이름</span>
                    <input
                        v-model="name"
                        class="input"
                        type="text"
                        name="username"
                        autocomplete="username"
                        placeholder="예: 김서연"
                        required
                    />
                </label>
                <label class="login-field">
                    <span>비밀번호</span>
                    <input
                        v-model="password"
                        class="input"
                        type="password"
                        name="password"
                        autocomplete="current-password"
                        placeholder="4자 이상"
                        required
                    />
                </label>
                <button class="btn btn-primary" type="submit" :disabled="isSaving">
                    {{ isSaving ? "확인 중..." : "로그인" }}
                </button>
            </form>
        </main>
    </div>
</template>

<style scoped src="../styles/components/login.css"></style>
