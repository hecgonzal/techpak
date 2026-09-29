# Ruppert working-log indexing

Ruppert keeps the raw master JSONL unchanged. Its separate working JSONL has two record kinds:

- `conversation_turn`: a small synchronous index for each new chat turn. Its `facts` contain deterministic key/value labels for the user call, assistant response, topic/intent and selected state fields.
- `condensed_master_record`: an offline adapter-generated index of every non-empty leaf value in one master record. Each fact has a JSON Pointer `source_path`, a short `key`, a concise `value`, and searchable `tags`. The source record ID allows auditing back to the master; the master remains authoritative.

## Run condensation during idle time

From the Ruppert-lite shell, run `/condense` to process up to 100 new master records, or `/condense 10` to set a smaller batch. This is explicit maintenance work, not part of a chat turn. It uses `working_log_adapter` in `config/device.json` (currently `Gemma3Adapter`; falls back to `ai_model` for older configs). It does not automatically detect idle time; the operator should run it when the device can spare inference resources.

Model output must be JSON and include one fact for every supplied non-empty source path. Missing, duplicate or invented paths, oversized records, invalid JSON and adapter errors are rejected; that master record stays unchanged and is reported as failed so it can be retried. Successful source IDs are skipped on later runs, making condensation idempotent for append-only master logs. Use a trusted local model adapter because master data is sent to the configured adapter.

Context lookup searches both normal turn fields and condensed fact keys, values, source paths and tags. It uses a small recent-turn window plus a bounded set of keyword-matched historical records. The implementation does not use embeddings or search the master log on the live chat path.
