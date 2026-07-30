<script setup>
import { onMounted, ref } from "vue";
import useAPI from "../composables/useApi";
import { useRouter } from "vue-router";

const router = useRouter();

const { getUsers, postUsers } = useAPI();

const users = ref([]);
const newUser = ref("");
const selectedUser = ref(localStorage.getItem("report-selectedUser") || "선택");

const setUser = () => {
    if (selectedUser.value === "선택") return alert("유저를 선택해주세요");
    localStorage.setItem("report-selectedUser", selectedUser.value);
    router.push("/");
};

const saveUser = async () => {
    const name = newUser.value.trim();
    if (!name) return alert("이름을 입력해주세요");
    try {
        await postUsers(name);
        newUser.value = "";
        // 생성 후 목록을 다시 불러와야 select 에 바로 나타난다.
        users.value = await getUsers();
        alert(`'${name}' 사용자를 생성했습니다.`);
    } catch (error) {
        console.error("사용자 생성 실패:", error);
        alert("사용자 생성에 실패했습니다. 중복된 이름인지 확인해주세요.");
    }
};

onMounted(async () => {
    const data = await getUsers();
    users.value = data;
    console.log(users.value);
});
</script>
<template>
    <div class="page">
        <div class="page-header">
            <div>
                <h1>사용자 선택</h1>
                <p class="page-subtitle">
                    보고서 작성자를 선택하거나 새로운 사용자를 생성하세요
                </p>
            </div>
        </div>

        <div class="card">
            <h2>사용자 선택</h2>
            <div class="field">
                <label for="user-select">사용자</label>
                <select id="user-select" v-model="selectedUser" class="input">
                    <option value="선택">선택</option>
                    <option
                        v-for="user in users"
                        :key="user.id"
                        :value="user.id"
                    >
                        {{ user.name }}
                    </option>
                </select>
            </div>

            <div class="form-actions">
                <button class="btn btn-primary" @click="setUser">선택</button>
            </div>
        </div>

        <div class="card">
            <h2>새 사용자 생성</h2>
            <div class="field">
                <label for="new-user">이름</label>
                <input
                    id="new-user"
                    type="text"
                    v-model="newUser"
                    class="input"
                    placeholder="사용자 이름을 입력하세요"
                    required
                />
            </div>

            <div class="form-actions">
                <button class="btn btn-primary" @click="saveUser">생성</button>
            </div>
        </div>
    </div>
</template>

<style scoped>
.form-actions {
    display: flex;
    justify-content: flex-end;
    margin-top: 16px;
}
</style>
