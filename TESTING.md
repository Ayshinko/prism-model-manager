# v0.1.0 candidate verification

Performed in isolated temporary HOME/XDG directories.

| Check | Result |
| --- | --- |
| ShellCheck 0.11.0, all shell files, sourced-file analysis | PASS, no diagnostics |
| Bash syntax | PASS |
| GGUF scanning and excluded adapters/projectors/partials | PASS |
| Config quoting, private permissions and model profile round trip | PASS |
| Shared command builder, spaces, LoRA/vision/reasoning options | PASS |
| Invalid context rejection and no-execution dry run | PASS |
| Existing local model and existing runtime launch-command dry run | PASS, command not executed |
| NVIDIA Ada fixture and unavailable-driver fallback | PASS |
| Log viewer invokes less with +F and correct file | PASS |
| Stale PID rejected; mock server start/stop | PASS |
| Install, overwrite refusal, installed execution, uninstall and data retention | PASS |
| GGUF metadata type mapping and truncated header rejection | PASS, 2 Python test methods |

No real model loaded, no API requests to an existing server, no model/runtime
artifacts downloaded, and no benchmarks executed. The current execution environment
could not query the NVIDIA driver; GPU classification was tested with fixtures.
Interactive gum rendering and real CUDA inference have not been certified.

The final source scan found no local username, private home path, storage mount,
private network address, credential assignment or private key material. Public
loopback addresses and API token-count fields in the benchmark helper are expected.
No weights, runtime executable, personal config, log or backup belongs to the staged
publication candidate. Raw historical source and config backups remain outside it.

The maintainer selected public distribution, delegated license choice (MIT),
and authorized repository creation, push and v0.1.0 publication.

The original manager and terminal launcher match their initial backup hashes.
The external LoRA scoring helper changed concurrently after backup; this candidate
retains its copied snapshot and does not overwrite or import those later changes.
