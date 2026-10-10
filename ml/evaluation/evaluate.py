from __future__ import annotations

import argparse

import numpy as np
from transformers import AutoModelForSequenceClassification, AutoTokenizer, Trainer

from ml.evaluation.metrics import compute_classification_metrics, confusion_matrix_as_list
from ml.preprocessing.dataset import load_text_classification_dataset, tokenize_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate a LexiTrace classifier.")
    parser.add_argument("--data", required=True)
    parser.add_argument("--model-dir", required=True)
    args = parser.parse_args()

    tokenizer = AutoTokenizer.from_pretrained(args.model_dir)
    model = AutoModelForSequenceClassification.from_pretrained(args.model_dir)
    dataset = tokenize_dataset(load_text_classification_dataset(args.data), tokenizer)
    trainer = Trainer(model=model, tokenizer=tokenizer, data_collator=__import__("transformers").DataCollatorWithPadding(tokenizer))
    predictions = trainer.predict(dataset["test"])
    predicted_labels = np.argmax(predictions.predictions, axis=-1)
    labels = predictions.label_ids
    print(compute_classification_metrics(labels, predicted_labels))
    print({"confusion_matrix": confusion_matrix_as_list(labels, predicted_labels)})


if __name__ == "__main__":
    main()
