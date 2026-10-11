// Phone capability states; the optional web/laptop bridge is reported separately.
// Replace this only after the named-device/runtime feasibility evidence exists.
export const AI_CAPABILITIES = Object.freeze({
  localInference: 'not_integrated',
  cloudAI: 'not_implemented',
  deterministicRecall: 'available',
  conversationAdapter: 'deterministic_prototype',
  camera: 'not_integrated',
  voice: 'not_integrated',
  nearby: 'no_pack',
  deviceNotifications: 'not_integrated',
  emailDelivery: 'not_connected',
} as const);

export const CAPABILITY_DETAILS = Object.freeze({
  camera: 'Camera and photo intake are not connected yet. Describe what you observed in chat; nothing is watched in the background.',
  voice: 'Voice is not connected yet. You can type the same request without granting microphone access.',
  model: 'Phone-local generation is not integrated. The optional laptop conversation bridge is separate. After a compatible phone model is qualified, Nook will handle setup in the app with your consent, size and storage checks, progress, retry, and verified offline readiness. No model is downloaded in this prototype.',
  nearby: 'No nearby data pack is installed. A future selected-area setup needs an initial connection and download approval. Cached results must show coverage and last refresh time.',
  cloud: 'Cloud AI is off and not connected. Future requests require a provider and your approval of the exact context to send.',
});
