<script setup>
defineProps({
    tabs: { type: Array, required: true },
    active: { type: String, default: "" },
});
</script>

<template>
    <nav class="app-tabs" role="tablist">
        <router-link
            v-for="tab in tabs"
            :key="tab.id"
            :to="tab.to"
            class="app-tab"
            role="tab"
            :aria-selected="active === tab.id"
            :class="{ 'is-active': active === tab.id }"
        >
            {{ tab.label }}
        </router-link>
    </nav>
</template>
