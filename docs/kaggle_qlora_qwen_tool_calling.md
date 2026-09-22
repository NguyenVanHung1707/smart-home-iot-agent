# QLoRA tool calling on Kaggle

This setup fine-tunes `Qwen/Qwen2.5-3B-Instruct` to emit the project's
validated `tool_calls` envelope. It trains a LoRA adapter, not a replacement
base model, and it never trains direct unlock or adversarial instructions.

## 1. Prepare the dataset locally

Run this from the repository root:

```bash
python scripts/generate_kaggle_tool_sft_dataset.py \
  --output-dir artifacts/qwen25_tool_sft
```

This produces `train.jsonl`, `validation.jsonl`, and a manifest. It contains
764 deterministic, schema-validated synthetic examples (690/74 at the default
split), including tool calls, ambiguity, negation, unsupported scheduling,
approval, and prompt-injection refusal. It rejects any exact benchmark holdout
utterance. Review synthetic examples with product/domain owners before calling
the dataset gold; add reviewed paraphrases only to training data.

## 2. Create Kaggle inputs

1. Create a private Kaggle Dataset and upload the generated JSONL.
2. Create a Notebook, attach that Dataset, enable a GPU accelerator and Internet.
3. If Hugging Face asks for access to the Qwen model, approve it on Hugging
   Face, then add `HF_TOKEN` as a Kaggle secret. The notebook reads it only at
   runtime and never prints it.
4. Upload/open `notebooks/kaggle_qwen25_tool_qlora.ipynb` and set
   `INPUT_JSONL` to the attached dataset path.

## 3. Outputs and validation

The notebook writes `qwen25-tool-calls-lora/` and a ZIP file under
`/kaggle/working/`. Download them as Kaggle output artifacts.

Keep the base Qwen2.5-3B model and load this adapter with PEFT for validation.
To serve it through the local GGUF/llama.cpp path, merge the adapter into the
matching base model and convert the merged model separately; do not claim that
an adapter alone is a GGUF model.

After export, benchmark with the untouched holdout and the same v7 harness.
Compare safety, unsafe-action rate, tool selection, and verified execution;
do not approve a model based on dashboard score alone.
