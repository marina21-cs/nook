# Model experiments disclosure

These are evaluated candidates, not Nook's accepted conversational engine. The published typed flow retrieves structured, confirmed records. Optional runtime speech uses Whisper tiny and Kokoro-82M.

| Candidate | Identity and terms | Scope and result |
| --- | --- | --- |
| [SmolVLM-500M-Instruct](https://huggingface.co/HuggingFaceTB/SmolVLM-500M-Instruct/tree/a7da5b986cb59b408707209984f360a5f4ad7e47) | Revision `a7da5b986cb59b408707209984f360a5f4ad7e47`; model.safetensors SHA256 `d05b567eeaf534e83d375551f068ed57b5f52d37c657197f644af5ef9db091a2`; Apache-2.0 | Isolated CPU FP32/default-processor benchmark on 9 October 2026. First image call returned no answer by 30.000523 seconds after 12.548393 seconds of model loading. Peak worker RSS: 4,203,753,472 bytes (3.915 GiB). Not integrated. A later reduced-resolution plan was blocked before model launch; it provides no successful inference or quality result. |
| [Qwen2.5 0.5B](https://ollama.com/library/qwen2.5:0.5b) | Pre-existing Ollama Q4_K_M candidate; digest `a8b0c51577010a279d933d14c2a8ab4b268079d44c5c8830c0a93900f1827c67`; Apache-2.0 metadata | Evaluated for bounded search-phrase normalization; disabled by default. No retrieval improvement over deterministic lookup established. |
| [Gemma 3 1B](https://ollama.com/library/gemma3:1b) | Pre-existing Ollama Q4_K_M candidate; digest `8648f39daa8fbf5b18c7b4e6a8fb4990c692751d49917417b8842ca5758e7ffc`; Gemma Terms | Same bounded normalization role; disabled by default. Not an accepted general conversational model or visual assistant. |

“0.5B” means approximately 500 million parameters. Small parameter counts were explored for constrained local execution, but parameter count alone does not establish usable memory, latency or answer quality. The SmolVLM run demonstrates that even this small candidate could exceed a useful interactive CPU budget in the tested configuration. It is not evidence that Nook is powered by a successfully deployed 0.5B conversational model.

Only this sanitized disclosure is published. No experimental model weights, private machine logs or benchmark runtimes are included. The supplied setup explicitly disables optional text normalization, detector inference and speech; the optional speech path has its own stated acceptance limitations.
