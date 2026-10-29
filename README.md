# mcp-demo

A tiny Python project prepared for a **GitHub MCP server** demo.

> ⚠️ `average()` in `stats.py` contains an **intentional bug** (it divides by `len(numbers) - 1` instead of `len(numbers)`). It is left there on purpose so the demo can show finding, reporting and fixing it through the GitHub MCP server. The `test_average` test is expected to fail on `main`.

## Run tests

```bash
pip install pytest
pytest
```
