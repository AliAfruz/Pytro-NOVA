# Security and data handling

Pytro-NOVA is an offline data viewer and extractor. It does not require cloud
accounts or send measurement files to a server. The .nox decoder parses
legacy serialized data as **data**, without invoking .NET BinaryFormatter.

Only open files from sources you trust. Third-party binary formats are complex;
no parser is guaranteed safe against all malformed or resource-exhaustion
inputs. Pytro-NOVA does not control a potentiostat or galvanostat.

Before publishing a GitHub repository, inspect its complete Git history and
working tree for real measurement files, confidential instrument metadata,
credentials, identifiers, and licensed third-party code. `.gitignore` does
not remove data already committed in Git history.

For a security report, use a private disclosure channel managed by the repository
owner rather than filing a public issue containing a sensitive proof of concept.
