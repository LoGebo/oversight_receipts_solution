"""QLoRA fine-tune of the pattern reviewer on a Modal GPU (free monthly credits).

  modal run modal_train.py                      # train on sft/train.jsonl, evaluate on sft/valid.jsonl
  modal run modal_train.py --base Qwen/Qwen3-14B --epochs 3

Data is uploaded from the local sft/ folder; the adapter and eval results are saved to the Modal volume
`reviewer-v2` and the eval JSON is also printed. No API keys are used or needed. Exam files (v2/e6) are never read.
"""
import json
import modal

app = modal.App("reviewer-v2")
vol = modal.Volume.from_name("reviewer-v2", create_if_missing=True)
image = (modal.Image.debian_slim(python_version="3.11")
         .pip_install("torch", "transformers>=4.51", "peft", "trl", "bitsandbytes", "accelerate", "datasets")
         .add_local_dir("sft", "/data"))


@app.function(image=image, gpu="A100-80GB", timeout=60 * 75, volumes={"/out": vol})
def train(base: str = "Qwen/Qwen3.5-9B", epochs: int = 3, lr: float = 2e-4):
    import torch
    from datasets import load_dataset
    from peft import LoraConfig
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from trl import SFTConfig, SFTTrainer

    tag = base.split("/")[-1]
    tok = AutoTokenizer.from_pretrained(base)
    kw = dict(torch_dtype=torch.bfloat16, device_map="auto",
              quantization_config=BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                                                     bnb_4bit_compute_dtype=torch.bfloat16))
    try:
        model = AutoModelForCausalLM.from_pretrained(base, **kw)
    except Exception as e:  # multimodal checkpoints (Qwen3.5) may only load through the image-text class
        print("CausalLM load failed, trying ImageTextToText:", repr(e)[:200])
        from transformers import AutoModelForImageTextToText
        model = AutoModelForImageTextToText.from_pretrained(base, **kw)
    raw = load_dataset("json", data_files={"train": "/data/train.jsonl", "valid": "/data/valid.jsonl"})

    def render(msgs):
        try:
            return tok.apply_chat_template(msgs[:2], tokenize=False, add_generation_prompt=True, enable_thinking=False)
        except TypeError:
            return tok.apply_chat_template(msgs[:2], tokenize=False, add_generation_prompt=True)

    def to_pc(r):
        return {"prompt": render(r["messages"]), "completion": r["messages"][2]["content"] + tok.eos_token}

    ds = raw.map(to_pc, remove_columns=["messages"])
    cfg = SFTConfig(output_dir=f"/out/{tag}/adapter", num_train_epochs=epochs, learning_rate=lr, per_device_train_batch_size=2,
                    gradient_accumulation_steps=4, logging_steps=5, eval_strategy="epoch", save_strategy="no",
                    bf16=True, max_length=6000, completion_only_loss=True, report_to=[], seed=2026)
    lora = LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05, task_type="CAUSAL_LM",
                      target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"])
    tr = SFTTrainer(model=model, args=cfg, train_dataset=ds["train"], eval_dataset=ds["valid"], peft_config=lora,
                    processing_class=tok)
    tr.train()
    tr.model.save_pretrained(f"/out/{tag}/adapter")

    # evaluation on the validation set: does the escalation list match the planted receipts?
    model = tr.model.eval()
    rows, hits, fraud_n, clean_n, fa = [], 0, 0, 0, 0
    import re
    for r, rr in zip(ds["valid"], raw["valid"]):
        gold = json.loads(rr["messages"][2]["content"])["escalate"]
        ids = {e["receipt_id"] for e in gold}
        x = tok(r["prompt"], return_tensors="pt", add_special_tokens=False).to(model.device)
        with torch.no_grad():
            y = model.generate(**x, max_new_tokens=300, do_sample=False)
        out = tok.decode(y[0][x["input_ids"].shape[1]:], skip_special_tokens=True)
        try:
            pred = {e["receipt_id"] for e in json.loads(out[out.index("{"):out.rindex("}") + 1])["escalate"]}
        except Exception:
            pred = None
        rows.append({"gold": sorted(ids), "pred": None if pred is None else sorted(pred), "raw": out[:300]})
        if ids:
            fraud_n += 1
            hits += int(bool(pred and pred & ids))
        else:
            clean_n += 1
            fa += int(bool(pred))
    res = {"base": base, "epochs": epochs, "history_recall": f"{hits}/{fraud_n}", "clean_false_alarms": f"{fa}/{clean_n}",
           "rows": rows}
    open(f"/out/{tag}/eval_valid.json", "w").write(json.dumps(res, indent=1))
    vol.commit()
    return {k: v for k, v in res.items() if k != "rows"}


@app.local_entrypoint()
def main(base: str = "Qwen/Qwen3.5-9B", epochs: int = 3):
    print(train.remote(base=base, epochs=epochs))
