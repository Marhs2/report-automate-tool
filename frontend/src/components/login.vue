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

<style scoped>
/* 카드 하나를 가운데 띄우지 않는다. 왼쪽은 이 도구가 만드는 결과(보고 한 장), 오른쪽은 폼. */
.login-page {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
    width: 100%;
    min-height: 100vh;
}

.login-side {
    display: flex;
    flex-direction: column;
    justify-content: center;
    gap: var(--space-5);
    padding: var(--space-8);
    border-right: 1px solid var(--border);
    background: var(--sidebar-bg);
}

.login-brand {
    margin: 0;
    font: var(--type-title);
    font-size: var(--fs-30);
    letter-spacing: -0.02em;
    color: var(--text-strong);
}

.login-lead {
    max-width: 420px;
    margin: 0;
    font-size: var(--fs-16);
    line-height: var(--lh-relaxed);
    color: var(--text);
    word-break: keep-all;
}

.login-sample {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    max-width: 420px;
    padding: var(--space-4) var(--space-5);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    background: var(--surface);
    box-shadow: var(--shadow-1);
}

.login-sample p {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    margin: 0;
    font-size: var(--fs-14);
    color: var(--text-strong);
}

.login-sample .login-sample-head {
    justify-content: space-between;
    margin-bottom: var(--space-1);
    padding-bottom: var(--space-2);
    border-bottom: 1px solid var(--border);
    font-weight: var(--fw-semibold);
}

.login-main {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: var(--space-8) var(--space-6);
}

.login-form {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
    width: min(360px, 100%);
}

.login-form .t-desc {
    margin-top: calc(-1 * var(--space-2));
}

.login-field {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    font: var(--type-caption);
    font-weight: var(--fw-semibold);
    color: var(--text-strong);
}

.login-field .input {
    height: var(--control-h-lg);
}

.login-form .btn {
    margin-top: var(--space-2);
    min-height: var(--control-h-lg);
}

@media (max-width: 860px) {
    .login-page {
        grid-template-columns: minmax(0, 1fr);
        grid-template-rows: auto 1fr;
    }

    .login-side {
        gap: var(--space-2);
        padding: calc(var(--space-7) + env(safe-area-inset-top, 0px)) var(--space-5) var(--space-5);
        border-right: 0;
        border-bottom: 1px solid var(--border);
    }

    .login-brand {
        font-size: var(--fs-24);
    }

    .login-lead {
        font-size: var(--fs-14);
    }

    .login-sample {
        display: none;
    }

    .login-main {
        align-items: flex-start;
        padding: var(--space-6) var(--space-5);
    }
}
</style>
