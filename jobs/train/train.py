# /// script
# requires-python = ">=3.11"
# dependencies = ["trl==0.29.1", "peft==0.18.1", "transformers==5.3.0", "datasets==4.5.0", "torch==2.10.0", "huggingface-hub==1.7.2"]
# ///
"""One multi-task Qwen3-4B LoRA. Evaluation loss is not a gold holdout score."""
import hashlib
import json
import os
from pathlib import Path


def validate_rows(rows: list[dict]) -> None:
    for row in rows:
        if (row.get('public') is not True or row.get('client_matter') is not False
                or row.get('scope') != 'platform' or row.get('region') != 'us-east'
                or row.get('holdout') is not False or row.get('active') is not True
                or 'tenant_id' in row or not row.get('task_type') or 'input' not in row or 'output' not in row):
            raise ValueError('Dataset contains unapproved or private rows')


def main() -> None:
    from datasets import Dataset
    from huggingface_hub import HfApi, hf_hub_download
    from peft import LoraConfig
    from trl import SFTConfig, SFTTrainer
    api = HfApi(token=os.environ['HF_TOKEN'])
    org, repo, day = os.environ['HF_ORG'], os.environ['OUTPUT_REPO'], os.environ['TRAIN_DAY']
    if api.model_info(repo).private is not True:
        raise ValueError('Model repository is not private')
    rows = []
    for agent in ('tank', 'base', 'tiger', 'market_lab', 'zenas', 'radix', 'tisan', 'rig'):
        dataset = f'{org}/tervory-public-{agent}'
        from huggingface_hub.errors import RepositoryNotFoundError, EntryNotFoundError
        try:
            info = api.dataset_info(dataset)
            if info.private is not True:
                raise ValueError('Dataset repository is not private')
            path = hf_hub_download(dataset, f'snapshots/us-east/{day}.jsonl', repo_type='dataset', revision=info.sha)
        except (RepositoryNotFoundError, EntryNotFoundError):
            continue
        batch = [json.loads(line) for line in Path(path).read_text().splitlines() if line]
        validate_rows(batch)  # Reject the entire run before constructing the trainer.
        rows.extend(batch)
    train, validation, seen = [], [], set()
    for row in rows:
        digest = hashlib.sha256(json.dumps(row['input'], sort_keys=True).encode()).hexdigest()
        if digest in seen:
            continue
        seen.add(digest)
        sample = {'prompt': [{'role': 'user', 'content': row['task_type'] + '\n' + json.dumps(row['input'])}],
                  'completion': [{'role': 'assistant', 'content': json.dumps(row['output'])}]}
        (validation if int(digest, 16) % 10 == 0 else train).append(sample)
    if not train or not validation:
        raise ValueError('Training and validation examples are required')
    trainer = SFTTrainer(model='Qwen/Qwen3-4B',
        args=SFTConfig(output_dir='/tmp/lora', num_train_epochs=1, max_length=1024,
                       per_device_train_batch_size=1, gradient_accumulation_steps=8,
                       gradient_checkpointing=True, bf16=True, report_to='none',
                       logging_strategy='no', save_strategy='no', push_to_hub=False),
        train_dataset=Dataset.from_list(train), eval_dataset=Dataset.from_list(validation),
        peft_config=LoraConfig(r=16, lora_alpha=32, target_modules='all-linear', task_type='CAUSAL_LM'))
    trainer.train()
    metrics = trainer.evaluate()
    trainer.save_model('/tmp/lora')
    Path('/tmp/lora/evaluation.json').write_text(json.dumps({'validation_loss': metrics['eval_loss'],
                                                          'n': len(validation), 'gold_holdout': False}))
    if api.model_info(repo).private is not True:
        raise ValueError('Output privacy changed')
    api.upload_folder(repo_id=repo, folder_path='/tmp/lora', commit_message='Multi-task LoRA and validation loss')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        raise SystemExit('Training failed; dataset, model and credential details are withheld.') from None
