<script setup>
defineProps({
    clickable: { type: Boolean, default: false },
});
</script>

<!-- One hairline-separated row: main | meta | actions (.app-list-row in components.css). -->
<template>
    <div class="app-list-row" :class="{ 'is-clickable': clickable }">
        <div class="app-list-row-main">
            <slot />
        </div>
        <div v-if="$slots.meta" class="app-list-row-meta">
            <slot name="meta" />
        </div>
        <div v-if="$slots.actions" class="app-list-row-actions" @click.stop>
            <slot name="actions" />
        </div>
    </div>
</template>
