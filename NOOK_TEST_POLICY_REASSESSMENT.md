> This document concerns older voice/typed checks. The separately accepted optional local-chat run used its own corrected model-capable supervisor and actual alarm/configured-high policy; see [current release](docs/CURRENT_RELEASE.md).

# Resource and inference scope for this export

The accepted expanded checkpoint ran deterministic backend and models-off browser checks.
No model worker was launched. Keep the application's existing thermal and resource guards.
The optional worker depends on Linux `/proc` and monitored `k10temp`/`spd5118` sensors,
and fails closed on unsupported devices. Never disable guards to imply portability.
Real speech, fresh installation and another device need separate monitored acceptance.
A Python socket guard does not establish OS-wide isolation.

The source owner's private sensor/process logs and machine paths are deliberately omitted.
See [public verification](docs/EXPANDED_VERIFICATION.json) and [voice setup](voice/SETUP.md).
