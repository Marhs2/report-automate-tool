<script setup>
defineProps({
    label: { type: String, default: "" },
    forId: { type: String, default: "" },
});
</script>

<!-- Label above control, 8px gap. Styling lives in components.css (.field / .field-label). -->
<template>
    <div class="field">
        <label v-if="label" class="field-label" :for="forId || undefined">{{ label }}</label>
        <slot />
    </div>
</template>
