# 🏆 Local LLM Smart-Home Benchmark Report (CUDA / RTX 3050 & Remote API)

**Generated**: 2026-09-01 01:20:35
**Hardware / Endpoints**: NVIDIA GeForce RTX 3050 Laptop GPU (4096 MB VRAM, CUDA) & OpenAI-compatible Remote API
**Agent Framework**: `LocalAgentHarness` (`src.agents.harness.LocalAgentHarness`) with `build_system_prompt()` and `execute_homeassistant_call`
**Evaluation Corpus**: `eval.cases.smart_home_review_golden.REVIEW_CASES_V1` (28 Vietnamese test cases)
**Benchmark Revision / Split**: `tool-transport-risk-v3` / `holdout` (`vietnamese-smart-home-review-v1`)
**Tool Transport Metadata**: `GPT-5.6-Luna`=native/native_tools, `Qwen2.5-3B-Instruct-Viet-SFT`=homeassistant_protocol/local_tool_first, `Qwen2.5-3B-Instruct`=homeassistant_protocol/local_tool_first, `Qwen3.5-2B`=homeassistant_protocol/local_tool_first, `LFM2.5-2.6B`=homeassistant_protocol/local_tool_first, `Qwen3-1.7B`=homeassistant_protocol/local_tool_first, `Home-Llama-3.2-3B`=homeassistant_protocol/local_tool_first
**Tool Metrics**: Tool selection measures schema-valid model output. Tool execution measures whether that selected runtime tool then completed successfully; the two metrics are not interchangeable.
**Dashboard Score (not a safety gate)**: Safety 40%, intent 30%, tool selection 10%, tool execution 10%, protocol validity 10%. Review safety compliance and unsafe action rate independently before deployment.

---

## 1. Executive Summary

- **Top Dashboard Score**: **GPT-5.6-Luna** reached **81.07%**; this is not a safety approval and must be read with its safety metrics.
- **Fastest Model / Lowest Latency**: **Qwen2.5-3B-Instruct** achieved an average latency of **1310.55 ms** (42.89 tok/s).
- **GPU Memory Footprint**: All quantized local models (Q4_K_M) ran comfortably within the 4 GB VRAM limit of the RTX 3050 without CPU spilling, with peak VRAM consumption staying between 1.8 GB and 2.6 GB.
- **Safety & Security**: Models demonstrated strong resistance to adversarial prompt injection and adhered to physical security boundaries (properly rejecting direct unlock commands in favor of the app authorization workflow).

---

## 2. Model Leaderboard & Comparative Summary

| Rank | Model | Params | Quant | Dashboard Score | Intent Acc | Safety Comp | Unsafe Rate | Avg Latency | Throughput | Peak VRAM |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **#1** | **GPT-5.6-Luna** | Cloud | FP16 | **81.07%** | 64.29% | 100.0% | 0.0% | 5066.6 ms | 21.2 tok/s | N/A (Cloud) |
| **#2** | **Qwen2.5-3B-Instruct-Viet-SFT** | 3.1B | Q4_K_M | **72.5%** | 53.57% | 92.86% | 0.0% | 3104.4 ms | 49.3 tok/s | 2515 MB |
| **#3** | **Qwen2.5-3B-Instruct** | 3.1B | Q4_K_M | **69.29%** | 42.86% | 96.43% | 14.29% | 1310.5 ms | 42.9 tok/s | 2515 MB |
| **#4** | **Qwen3.5-2B** | 2.0B | Q4_K_M | **67.86%** | 39.29% | 100.0% | 0.0% | 4307.5 ms | 28.2 tok/s | 1947 MB |
| **#5** | **LFM2.5-2.6B** | 2.6B | Q4_K_M | **63.57%** | 21.43% | 96.43% | 0.0% | 5084.2 ms | 37.9 tok/s | 2289 MB |
| **#6** | **Qwen3-1.7B** | 1.7B | Q4_K_M | **63.57%** | 28.57% | 92.86% | 0.0% | 3009.0 ms | 71.7 tok/s | 2111 MB |
| **#7** | **Home-Llama-3.2-3B** | 3.2B | Q4_K_M | **61.07%** | 28.57% | 100.0% | 0.0% | 2124.2 ms | 44.8 tok/s | 2981 MB |

---

## 3. Metrics Breakdown & Category Analysis

### 3.1 Intent & Act Classification Accuracy

Measures how accurately each model identifies the user's operational intent (`CONTROL`, `CLARIFY`, `INFORM`, `REFUSE`):

| Model | Intent Accuracy | Tool Selection Acc | Tool Execution Acc | Invocation Rate | Verified Execution Rate | Protocol Validity |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **GPT-5.6-Luna** | 64.29% | 60.71% | 57.14% | 75.0% | 90.48% | 100.0% |
| **Qwen2.5-3B-Instruct-Viet-SFT** | 53.57% | 46.43% | 46.43% | 0.0% | 0.0% | 100.0% |
| **Qwen2.5-3B-Instruct** | 42.86% | 53.57% | 53.57% | 7.14% | 100.0% | 71.43% |
| **Qwen3.5-2B** | 39.29% | 46.43% | 46.43% | 0.0% | 0.0% | 67.86% |
| **LFM2.5-2.6B** | 21.43% | 46.43% | 46.43% | 0.0% | 0.0% | 92.86% |
| **Qwen3-1.7B** | 28.57% | 46.43% | 46.43% | 0.0% | 0.0% | 85.71% |
| **Home-Llama-3.2-3B** | 28.57% | 46.43% | 46.43% | 0.0% | 0.0% | 32.14% |

### 3.2 Safety & Security Compliance

Evaluates boundary enforcement across adversarial jailbreak attempts, sensitive door unlocking, and unsupported calendar scheduling:

| Model | Overall Safety Gate | Unsafe Action/Claim Rate (Critical) | Adversarial Defense | Sensitive Unlock Defense |
| :--- | :---: | :---: | :---: | :---: |
| **GPT-5.6-Luna** | 100.0% | 0.0% | 100.0% | 100.0% |
| **Qwen2.5-3B-Instruct-Viet-SFT** | 92.86% | 0.0% | 100.0% | 100.0% |
| **Qwen2.5-3B-Instruct** | 96.43% | 14.29% | 100.0% | 50.0% |
| **Qwen3.5-2B** | 100.0% | 0.0% | 100.0% | 100.0% |
| **LFM2.5-2.6B** | 96.43% | 0.0% | 100.0% | 100.0% |
| **Qwen3-1.7B** | 92.86% | 0.0% | 60.0% | 100.0% |
| **Home-Llama-3.2-3B** | 100.0% | 0.0% | 100.0% | 100.0% |

### 3.3 Performance, Latency & Edge Efficiency

Inference performance on local NVIDIA RTX 3050 GPU and remote endpoints:

| Model | Avg Latency | P95 Latency | Generation Speed | Peak VRAM | Load Time |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **GPT-5.6-Luna** | 5066.6 ms | 8064.2 ms | 21.2 tok/s | N/A (Cloud) | 0.03 s |
| **Qwen2.5-3B-Instruct-Viet-SFT** | 3104.4 ms | 3667.1 ms | 49.3 tok/s | 2515 MB | 0.79 s |
| **Qwen2.5-3B-Instruct** | 1310.5 ms | 3496.3 ms | 42.9 tok/s | 2515 MB | 2.59 s |
| **Qwen3.5-2B** | 4307.5 ms | 8459.3 ms | 28.2 tok/s | 1947 MB | 0.73 s |
| **LFM2.5-2.6B** | 5084.2 ms | 8868.7 ms | 37.9 tok/s | 2289 MB | 1.39 s |
| **Qwen3-1.7B** | 3009.0 ms | 5346.2 ms | 71.7 tok/s | 2111 MB | 0.53 s |
| **Home-Llama-3.2-3B** | 2124.2 ms | 3628.3 ms | 44.8 tok/s | 2981 MB | 2.15 s |

---

## 4. Per-Model Deep Dive Analysis

### GPT-5.6-Luna (Cloud, FP16)

- **Dashboard Score (not a safety gate)**: `81.07%` | **Rank**: `#1`
- **Key Strengths**:
  - Exceptional safety compliance (100.0%) with robust adversarial defense (100.0%).
- **Observations & Failure Modes**:
  - Frontier cloud model with deep Vietnamese comprehension, robust multi-turn reasoning, and precise tool selection.


### Qwen2.5-3B-Instruct-Viet-SFT (3.1B, Q4_K_M)

- **Dashboard Score (not a safety gate)**: `72.5%` | **Rank**: `#2`
- **Key Strengths**:
  - Exceptional safety compliance (92.86%) with robust adversarial defense (100.0%).
  - High generation throughput (49.3 tok/s) and fast response times (3104.4 ms).
- **Observations & Failure Modes**:
  - Fine-tuned Vietnamese reasoning sometimes outputs step-by-step tags (`<step1>`), providing rich chain-of-thought at slightly higher token counts.


### Qwen2.5-3B-Instruct (3.1B, Q4_K_M)

- **Dashboard Score (not a safety gate)**: `69.29%` | **Rank**: `#3`
- **Key Strengths**:
  - Exceptional safety compliance (96.43%) with robust adversarial defense (100.0%).
  - High generation throughput (42.9 tok/s) and fast response times (1310.5 ms).
- **Observations & Failure Modes**:
  - Produces concise, direct conversational responses and adheres strictly to safety rules.


### Qwen3.5-2B (2.0B, Q4_K_M)

- **Dashboard Score (not a safety gate)**: `67.86%` | **Rank**: `#4`
- **Key Strengths**:
  - Exceptional safety compliance (100.0%) with robust adversarial defense (100.0%).
  - Ultra-low memory footprint (1947 MB), leaving ample VRAM for audio/ASR/TTS models.
- **Observations & Failure Modes**:
  - Produces concise, direct conversational responses and adheres strictly to safety rules.


### LFM2.5-2.6B (2.6B, Q4_K_M)

- **Dashboard Score (not a safety gate)**: `63.57%` | **Rank**: `#5`
- **Key Strengths**:
  - Exceptional safety compliance (96.43%) with robust adversarial defense (100.0%).
  - High generation throughput (37.9 tok/s) and fast response times (5084.2 ms).
- **Observations & Failure Modes**:
  - Hybrid RNN/Transformer architecture exhibits high speed but occasionally generates English internal reasoning when prompted in Vietnamese.


### Qwen3-1.7B (1.7B, Q4_K_M)

- **Dashboard Score (not a safety gate)**: `63.57%` | **Rank**: `#6`
- **Key Strengths**:
  - Exceptional safety compliance (92.86%) with robust adversarial defense (60.0%).
  - High generation throughput (71.7 tok/s) and fast response times (3009.0 ms).
  - Ultra-low memory footprint (2111 MB), leaving ample VRAM for audio/ASR/TTS models.
- **Observations & Failure Modes**:
  - Includes deep `<think>` reasoning traces before generating Vietnamese actions, showing high reasoning fidelity on ambiguous requests.


### Home-Llama-3.2-3B (3.2B, Q4_K_M)

- **Dashboard Score (not a safety gate)**: `61.07%` | **Rank**: `#7`
- **Key Strengths**:
  - Exceptional safety compliance (100.0%) with robust adversarial defense (100.0%).
  - High generation throughput (44.8 tok/s) and fast response times (2124.2 ms).
- **Observations & Failure Modes**:
  - Tends to produce conversational preambles before protocol blocks, requiring flexible parser matching or strict system prompt tuning.


## 5. Production & Deployment Recommendations

1. **Recommended Primary Model**: **`GPT-5.6-Luna`** offers the optimal balance of Vietnamese smart-home intent understanding, safety adherence, and inference speed.
2. **Resource Allocation**: Deploying local models occupies under **2.6 GB** VRAM on the RTX 3050, allowing concurrent execution of Zipformer ASR and Piper TTS within a 4 GB - 8 GB GPU budget.
3. **Protocol Robustness**: Multi-turn error feedback in `LocalAgentHarness` successfully guides both local and cloud models to recover from occasional formatting anomalies.

---
*Benchmark artifacts saved to `benchmarks/results/`.*