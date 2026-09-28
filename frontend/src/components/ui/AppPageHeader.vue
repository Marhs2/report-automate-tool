<script setup>
defineProps({
    title: { type: String, default: "" },
    subtitle: { type: String, default: "" },
});
</script>

<!-- Title/subtitle on the left, filters then actions on the right (.page-header in shell.css). -->
<template>
    <header class="page-header">
        <div v-if="title || subtitle" class="page-header-text">
            <h1 v-if="title" class="page-title">{{ title }}</h1>
            <p v-if="subtitle" class="page-subtitle">{{ subtitle }}</p>
        </div>
        <div v-if="$slots.filters" class="page-header-filters">
            <slot name="filters" />
        </div>
        <div v-if="$slots.actions" class="page-header-actions">
            <slot name="actions" />
        </div>
    </header>
</template>
