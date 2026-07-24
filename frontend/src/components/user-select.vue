<script setup>
import { onMounted, ref } from "vue";
import useAPI from "../composables/useApi";

const { getUsers, postUsers } = useAPI();

const users = ref([]);
const newUser = ref("");
const selectedUser = ref(sessionStorage.getItem("selectedUser") || "선택");

const setUser = () => {
    if (selectedUser.value === "선택") return alert("유저를 선택해주세요");
    sessionStorage.setItem("selectedUser", selectedUser.value);
};

const saveUser = async () => {
    const res = await postUsers(newUser.value);
    window.location.reload();
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
