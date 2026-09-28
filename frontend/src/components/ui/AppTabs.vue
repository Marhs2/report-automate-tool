<script setup>
defineProps({
    tabs: { type: Array, required: true },
    active: { type: String, default: "" },
});
</script>

<!-- Underline tabs on one hairline (.app-tabs / .app-tab in components.css). -->
<template>
    <nav class="app-tabs" role="tablist">
        <router-link
            v-for="tab in tabs"
            :key="tab.id"
            :to="tab.to"
            class="app-tab"
            role="tab"
            :aria-selected="active === tab.id"
            :aria-current="active === tab.id ? 'page' : undefined"
            :class="{ 'is-active': active === tab.id }"
        >
            {{ tab.label }}
        </router-link>
    </nav>
</template>
