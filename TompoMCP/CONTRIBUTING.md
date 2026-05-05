# Contributing to TompoMCP

This project welcomes contributions and suggestions. Most contributions require
you to agree to a Contributor License Agreement (CLA) declaring that you have
the right to, and actually do, grant us the rights to use your contribution.
For details, visit https://cla.opensource.microsoft.com.

When you submit a pull request, a CLA bot will automatically determine whether
you need to provide a CLA and decorate the PR appropriately (e.g., status check,
comment). Simply follow the instructions provided by the bot. You will only need
to do this once across all repos using our CLA.

This project has adopted the
[Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/).
For more information see the
[Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or
contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any
additional questions or comments.

## How to Contribute

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-improvement`)
3. Make your changes
4. Run tests: `python -m pytest tests/`
5. Commit with a clear message
6. Push and open a Pull Request

## Development Setup

```bash
git clone https://github.com/microsoft/HRDIUtilities.git
cd HRDIUtilities/TompoMCP
pip install -e .
python -m pytest tests/
```

## Reporting Issues

Use [GitHub Issues](https://github.com/microsoft/HRDIUtilities/issues) to report
bugs or suggest features. Please include:

- Steps to reproduce
- Expected vs actual behavior
- Python version and OS
- Relevant error messages or logs
