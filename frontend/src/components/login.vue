<script setup>
import { ref } from "vue";
import { useRouter } from "vue-router";
import useApi from "../composables/useApi";
import { isAdmin, sessionToken } from "../composables/useSession";
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
        <form class="card login-card" @submit.prevent="login">
            <h1>로그인</h1>
            <label class="login-field">
                <span>이름</span>
                <input
                    v-model="name"
                    class="input"
                    type="text"
                    name="username"
                    autocomplete="username"
                    placeholder="이름"
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
    </div>
</template>

<style scoped>
.login-page {
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: var(--space-5);
    width: 100%;
}

.login-card {
    width: min(400px, 100%);
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    padding: var(--space-6);
margin: 0 auto;
}

.login-kicker {
    margin: 0;
    font-size: var(--fs-12);
    font-weight: var(--fw-semibold);
    letter-spacing: 0.6px;
    color: var(--text);
}

.login-card h1 {
    margin: 0;
    font-family: var(--heading);
    font-size: 24px;
    letter-spacing: -0.3px;
    color: var(--text-strong);
}

.login-help {
    margin: 0 0 var(--space-2);
    font-size: var(--fs-13);
    color: var(--text);
    word-break: keep-all;
}

.login-field {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    font-size: var(--fs-13);
    font-weight: var(--fw-semibold);
    color: var(--text-strong);
}

.login-card .btn {
    margin-top: var(--space-2);
    min-height: 44px;
}
</style>
