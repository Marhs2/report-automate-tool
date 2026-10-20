<script setup>
import { computed } from "vue";
import { ArrowRight, CircleCheck, CircleDashed, Folder, Hand, TriangleAlert } from "lucide-vue-next";

const props = defineProps({
    kind: { type: String, required: true },
    label: { type: String, required: true },
    bare: { type: Boolean, default: false },
    iconOnly: { type: Boolean, default: false },
});

const KINDS = {
    project: { icon: Folder, tag: "" },
    done: { icon: CircleCheck, tag: "is-done" },
    progress: { icon: CircleDashed, tag: "is-progress" },
    issue: { icon: TriangleAlert, tag: "is-issue" },
    request: { icon: Hand, tag: "is-request" },
    next: { icon: ArrowRight, tag: "is-next" },
};

const entry = computed(() => KINDS[props.kind] || KINDS.project);
</script>

<template>
    <span v-if="iconOnly" class="kind-icon" :class="entry.tag" :title="label">
        <component :is="entry.icon" :size="18" :stroke-width="2.25" aria-hidden="true" />
    </span>
    <span v-else class="kind-tag" :class="bare ? 'is-bare' : ['cat-tag', entry.tag]">
        <component :is="entry.icon" :size="13" :stroke-width="2.25" aria-hidden="true" />
        {{ label }}
    </span>
</template>

<style scoped src="../../styles/components/ui/KindTag.css"></style>
