from __future__ import annotations

from datasets import Dataset, DatasetDict, load_dataset


def load_text_classification_dataset(path: str) -> DatasetDict:
    dataset = load_dataset("csv", data_files=path)["train"]
    split = dataset.train_test_split(test_size=0.2, seed=42)
    validation_test = split["test"].train_test_split(test_size=0.5, seed=42)
    return DatasetDict(
        {
            "train": split["train"],
            "validation": validation_test["train"],
            "test": validation_test["test"],
        }
    )


def tokenize_dataset(dataset: DatasetDict, tokenizer, max_length: int = 256) -> DatasetDict:
    def tokenize(batch: Dataset) -> dict:
        return tokenizer(batch["text"], truncation=True, padding="max_length", max_length=max_length)

    return dataset.map(tokenize, batched=True)
