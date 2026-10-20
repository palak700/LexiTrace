"""Labels of the existing document checkpoint, restored with user approval."""
LABELS = ['Human', 'AI-Generated', 'AI-Edited Human']


def encode_label(value):
    value = str(value).strip()
    if value in tuple(str(index) for index in range(len(LABELS))):
        return int(value)
    if value in LABELS:
        return LABELS.index(value)
    raise ValueError(f'Invalid label {value!r}; expected Human, AI-Generated or AI-Edited Human (0/1/2).')


def checkpoint_indices(labels):
    if len(labels) != len(LABELS) or set(labels) != set(LABELS):
        raise ValueError('Incompatible checkpoint: expected exactly three classes: Human, AI-Generated, and AI-Edited Human. Provide a checkpoint trained for these classes; outputs cannot be silently relabeled or merged.')
    return [labels.index(label) for label in LABELS]
