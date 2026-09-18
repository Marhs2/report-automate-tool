<script setup>
defineProps({
    label: { type: String, default: "" },
    forId: { type: String, default: "" },
});
</script>

<template>
    <div class="field">
        <label v-if="label" :for="forId || undefined">{{ label }}</label>
        <slot />
    </div>
</template>
