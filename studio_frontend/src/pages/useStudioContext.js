import { inject } from "vue";

export function useStudioContext(componentName = "StudioPage") {
  const context = inject("studioContext");
  if (!context) {
    throw new Error(`${componentName} must be used inside App.vue studioContext provider.`);
  }
  return context;
}
