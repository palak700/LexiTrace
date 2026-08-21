from __future__ import annotations

import argparse

import numpy as np
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    DataCollatorWithPadding,
    Trainer,
    TrainingArguments,
)

from ml.evaluation.metrics import compute_classification_metrics
from ml.preprocessing.dataset import load_text_classification_dataset, tokenize_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description="Fine-tune DeBERTa-v3-base for LexiTrace.")
    parser.add_argument("--data", required=True, help="CSV path with text,label columns.")
    parser.add_argument("--output-dir", default="ml/models/deberta-v3-base-finetuned")
    parser.add_argument("--model-name", default="microsoft/deberta-v3-base")
    parser.add_argument("--epochs", type=float, default=3)
    parser.add_argument("--batch-size", type=int, default=8)
    args = parser.parse_args()

    tokenizer = AutoTokenizer.from_pretrained(args.model_name)
    dataset = tokenize_dataset(load_text_classification_dataset(args.data), tokenizer)

    model = AutoModelForSequenceClassification.from_pretrained(
        args.model_name,
        num_labels=4,
        id2label={0: "Human", 1: "AI-generated", 2: "AI-polished human", 3: "Humanized AI"},
        label2id={"Human": 0, "AI-generated": 1, "AI-polished human": 2, "Humanized AI": 3},
    )

    def metrics(eval_pred):
        logits, labels = eval_pred
        predictions = np.argmax(logits, axis=-1)
        return compute_classification_metrics(labels, predictions)

    training_args = TrainingArguments(
        output_dir=args.output_dir,
        eval_strategy="epoch",
        save_strategy="epoch",
        learning_rate=2e-5,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        num_train_epochs=args.epochs,
        weight_decay=0.01,
        load_best_model_at_end=True,
        metric_for_best_model="f1_macro",
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=dataset["train"],
        eval_dataset=dataset["validation"],
        tokenizer=tokenizer,
        data_collator=DataCollatorWithPadding(tokenizer),
        compute_metrics=metrics,
    )
    trainer.train()
    trainer.evaluate(dataset["test"])
    trainer.save_model(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)


if __name__ == "__main__":
    main()
