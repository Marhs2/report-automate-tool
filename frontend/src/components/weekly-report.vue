<script setup>
import { ref } from "vue";
import useExport from "../composables/useExport";

const { exportDocx } = useExport();

const selects = ref([]);
const userId = ref();

const date = new Date();
const day = date.getDay();
const getThisWeek = () => {
    const diffToMonday = date.getDate() - (day === 0 ? 7 : day) + 1;
    const monday = new Date(date.setDate(diffToMonday));

    const formatDate = (d) => d.toISOString().split("T")[0];

    return {
        monday: formatDate(monday),
    };
};

const sendDates = async () => {
  const response = await exportDocx(userId.value, selects.value);
  console.log(response);};

const { monday } = getThisWeek();
</script>

<template>
    <div>
        <ul v-for="day in 7">
            <li>
                {{
                    new Date(
                        new Date(monday).setDate(
                            new Date(monday).getDate() + (day - 1),
                        ),
                    )
                        .toISOString()
                        .split("T")[0]
                }}
            </li>
            <li>
                <input
                    type="checkbox"
                    v-model="selects"
                    :value="
                        new Date(
                            new Date(monday).setDate(
                                new Date(monday).getDate() + (day - 1),
                            ),
                        )
                            .toISOString()
                            .split('T')[0]
                    "
                />
            </li>
        </ul>

        <ul>
            <input type="number" placeholder="user Id" v-model="userId" />
            <button v-on:click="() => sendDates()">주간 보고서 생성</button>
        </ul>
    </div>
</template>

<style>
li,
ul {
    list-style: none;
}
ul {
    display: flex;
    align-items: center;
}
</style>
