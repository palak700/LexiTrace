# Dataset Format

Use CSV files with this schema:

```csv
text,label
"Human written example...",0
"AI generated example...",1
"Human text improved by AI...",2
"AI text rewritten to appear human...",3
```

Labels:

- `0`: Human
- `1`: AI-generated
- `2`: AI-polished human
- `3`: Humanized AI

Datasets such as APT-Eval, RAID, and Beemo can be integrated by mapping their source labels into this four-class taxonomy and saving CSV files in this format. Keep large datasets out of Git.
