<script setup>
import { ref } from "vue";

const users = ref([
    { id: 1, name: "User 1" },
    { id: 2, name: "User 2" },
    { id: 3, name: "User 3" },
]);
const newUser = ref("");

const createUser = () => {
    users.value.push({ id: users.value.length + 1, name: newUser.value });
};
</script>
<template>
    <div>
        <select>
            <option v-for="user in users" :key="user.id" :value="user.id">
                {{ user.name }}
            </option>
        </select>

        <button @click="selectUser">Select</button>
    </div>

    <div>만약 사용자가 없다면 생성하세요</div>
    <input type="text" v-model="newUser" />
    <button @click="createUser">Create</button>
</template>
