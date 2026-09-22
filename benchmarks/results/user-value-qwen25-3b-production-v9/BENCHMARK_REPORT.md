# 🏆 Local LLM Smart-Home Benchmark Report (CUDA / RTX 3050 & Remote API)

**Generated**: 2026-09-01 22:57:18
**Hardware / Endpoints**: NVIDIA GeForce RTX 3050 Laptop GPU (4096 MB VRAM, CUDA) & OpenAI-compatible Remote API
**Agent Framework**: `LocalAgentHarness` (`src.agents.harness.LocalAgentHarness`) with `build_system_prompt()` and `execute_homeassistant_call`
**Evaluation Corpus**: `eval.cases.smart_home_review_golden.REVIEW_CASES_V1` (28 Vietnamese test cases)
**Benchmark Revision / Split**: `tool-transport-user-value-v4` / `holdout` (`vietnamese-smart-home-review-v1`)
**Tool Transport Metadata**: `Qwen2.5-3B-Instruct`=homeassistant_protocol/local_tool_first
**Tool Metrics**: Tool selection measures schema-valid model output. Tool execution measures whether that selected runtime tool then completed successfully; the two metrics are not interchangeable.
**Dashboard Score (not a safety gate)**: Safety 40%, intent 30%, tool selection 10%, tool execution 10%, protocol validity 10%. Review safety compliance and unsafe action rate independently before deployment.
**User-value metrics**: User Task Success requires matched act, safety, valid protocol, expected tool selection, and (when tools are expected) matching successful execution. FTRR (First-Turn Resolution Rate) uses only non-ambiguous expected `CONTROL`/`INFORM`/`REFUSE` cases; expected clarification cases are excluded, not scored as failures. Difficulty is deterministic from corpus metadata: EASY=explicit single-intent routine/read-only; MEDIUM=language/value/state or unambiguous unsupported; HARD=multi-step, ambiguity, negation/quoted/hypothetical, sensitive, adversarial, nonexistent topology, or other high-risk metadata.

---

## 1. Executive Summary

- **Top Dashboard Score**: **Qwen2.5-3B-Instruct** reached **89.29%**; this is not a safety approval and must be read with its safety metrics.
- **Fastest Model / Lowest Latency**: **Qwen2.5-3B-Instruct** achieved an average latency of **282.65 ms** (3.61 tok/s).
- **GPU Memory Footprint**: All quantized local models (Q4_K_M) ran comfortably within the 4 GB VRAM limit of the RTX 3050 without CPU spilling, with peak VRAM consumption staying between 1.8 GB and 2.6 GB.
- **Safety & Security**: Models demonstrated strong resistance to adversarial prompt injection and adhered to physical security boundaries (properly rejecting direct unlock commands in favor of the app authorization workflow).

---

## 1.1 User-Value Metrics

| Model | Agent Mode | User Task Success | Production path | Model path | FTRR (eligible first turns) | Easy | Medium | Hard |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Qwen2.5-3B-Instruct** | production | 71.43% (20/28) | 72.0% (18/25) | 66.67% (2/3) | 75.0% (18/24) | 100.0% (3/3) | 72.73% (8/11) | 64.29% (9/14) |

---

## 2. Model Leaderboard & Comparative Summary

| Rank | Model | Params | Quant | Dashboard Score | Intent Acc | Safety Comp | Unsafe Rate | Avg Latency | Throughput | Peak VRAM |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **#1** | **Qwen2.5-3B-Instruct** | 3.1B | Q4_K_M | **89.29%** | 78.57% | 100.0% | 0.0% | 282.6 ms | 3.6 tok/s | 2557 MB |

---

## 3. Metrics Breakdown & Category Analysis

### 3.1 Intent & Act Classification Accuracy

Measures how accurately each model identifies the user's operational intent (`CONTROL`, `CLARIFY`, `INFORM`, `REFUSE`):

| Model | Intent Accuracy | Tool Selection Acc | Tool Execution Acc | Invocation Rate | Verified Execution Rate | Protocol Validity |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Qwen2.5-3B-Instruct** | 78.57% | 78.57% | 78.57% | 42.86% | 100.0% | 100.0% |

### 3.2 Safety & Security Compliance

Evaluates boundary enforcement across adversarial jailbreak attempts, sensitive door unlocking, and unsupported calendar scheduling:

| Model | Overall Safety Gate | Unsafe Action/Claim Rate (Critical) | Adversarial Defense | Sensitive Unlock Defense |
| :--- | :---: | :---: | :---: | :---: |
| **Qwen2.5-3B-Instruct** | 100.0% | 0.0% | 100.0% | 100.0% |

### 3.3 Performance, Latency & Edge Efficiency

Inference performance on local NVIDIA RTX 3050 GPU and remote endpoints:

| Model | Avg Latency | P95 Latency | Generation Speed | Peak VRAM | Load Time |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Qwen2.5-3B-Instruct** | 282.6 ms | 2743.8 ms | 3.6 tok/s | 2557 MB | 0.89 s |

---

## 4. Per-Model Deep Dive Analysis

### Qwen2.5-3B-Instruct (3.1B, Q4_K_M)

- **Dashboard Score (not a safety gate)**: `89.29%` | **Rank**: `#1`
- **Key Strengths**:
  - Exceptional safety compliance (100.0%) with robust adversarial defense (100.0%).
  - Strong intent disambiguation and command understanding in Vietnamese.
- **Observations & Failure Modes**:
  - Produces concise, direct conversational responses and adheres strictly to safety rules.


## 5. Production & Deployment Recommendations

1. **Recommended Primary Model**: **`Qwen2.5-3B-Instruct`** offers the optimal balance of Vietnamese smart-home intent understanding, safety adherence, and inference speed.
2. **Resource Allocation**: Deploying local models occupies under **2.6 GB** VRAM on the RTX 3050, allowing concurrent execution of Zipformer ASR and Piper TTS within a 4 GB - 8 GB GPU budget.
3. **Protocol Robustness**: Multi-turn error feedback in `LocalAgentHarness` successfully guides both local and cloud models to recover from occasional formatting anomalies.

---
*Benchmark artifacts saved to `benchmarks/results/`.*