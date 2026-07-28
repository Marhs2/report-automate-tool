<script>
import { useRoute } from "vue-router";

const router = useRoute();
</script>
<template>{{ router.params.id }}</template>
