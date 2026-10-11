# Laptop-local conversation checkpoint — 11 October 2026

Historical pre-adapter checkpoint, now resumed. The bounded adapter, actual-Qwen results and cleanup are recorded in [the current receipt](LAPTOP_CONVERSATION_RECEIPT.md); use [the run guide](LAPTOP_CONVERSATION_RUN_GUIDE.md). The original checkpoint below remains as provenance.

The user corrected ongoing work to GPT-6.1 Sol **High**, superseding Max. This turn ends at a short safe checkpoint because active inference settings cannot be changed through this executor mid-turn. No adapter code or inference was started; the tested Expo source remains unchanged. The next turn must use the requested High setting. Runtime identity/settings are not independently exposed by these tools.

Read-only inspection verified Ollama client and existing localhost runtime **0.30.6** on **127.0.0.1:11434**. Its `/api/tags` lists **qwen2.5:0.5b**, manifest digest **a8b0c51577010a279d933d14c2a8ab4b268079d44c5c8830c0a93900f1827c67**, **397,821,319 bytes**, **Q4_K_M**, **494.03M** parameters. `/api/ps` reports no models loaded. This pre-existing service was neither started nor stopped here. The initial sandboxed CLI could not connect; the approved read-only loopback route supplied the reliable status. Do not equate that earlier connection warning with a stopped service.

The separate existing project cache at `docs/candidates/local-chat-20261010/acquisition/artifacts` is complete. Its pinned `qwen2.5:0.5b-instruct-q4_K_M` manifest and all five configuration/model/system/template/license blobs passed byte-size and SHA-256 checks. The retained config identifies GGUF/Qwen2/Q4_K_M. No download occurred. An existing Ollama key file is present; no key was created or printed.

All **37 maintained Expo files** match the completed chat milestone validation. No regression tests were rerun and no real generated output, latency or quality is claimed. There are no owned model, browser, bridge or other heavy processes running. The existing 11434 service remains untouched.

Resume by preserving the last tested source snapshot, implementing a bounded same-origin web/host adapter, and using an owned loopback runtime for complete process supervision if needed. Port 11439 was free during inspection; recheck before startup. Use only the verified existing cache and installed binary, cloud disabled, CPU-only, one limited request at a time, bounded context/output/timeout and the existing resource guards. Do not weaken alarms, memory/swap/CPU protections or kill the unrelated service. The model supervisor in `docs/candidates/local-chat-20261010/model_guard.py` has the complete non-main-thread descendant supervision retained from the prior reviewed run; its old evidence is historical, not a new qualification.

Keep confirmed personal facts on the deterministic source-card path. A model receives no write authority; any proposed action must pass schema validation and exact preview approval. Label generated conversation **laptop-local model**, never on-phone offline. Test greeting/follow-up/context, unknown/conflicting memories, malicious notes/tool arguments, cancellation, timeout and service-offline fallback. Separate fixture tests from actual generated-output assessment.

APK/Gradle/prebuild/device installs, model downloads, new providers/credentials, external email, push and deployment remain out of scope. Device/runtime/pack qualification remains a later gate.

[Inventory and hashes](evidence/20261011/laptop-model/inventory-checkpoint.json), [last tested Expo receipt](EXPO_CHAT_RECEIPT.md), [source recovery](evidence/20261011/chat/recovery.json). Official protocol references: [Ollama chat API](https://docs.ollama.com/api/chat), [cloud-disable/local runtime FAQ](https://docs.ollama.com/faq).
