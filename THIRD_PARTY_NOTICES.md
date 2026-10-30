# Component and artwork provenance

The original application archive's MIT copyright notice is preserved in `LICENSE`.
This release is prepared and maintained for Ali Afruz under the Pytro-NOVA name.

## EIS numerical engine

`backend/afr_eis/models.py`, `fitting.py` and `diagnostics.py` match the files in
[AliAfruz/EIS-studio](https://github.com/AliAfruz/EIS-studio) at commit
`697fc2ff759cae2d94fd3418ccf794834c22164d`, byte for byte. Their MIT copyright is
**2026 Ali Afruz and Maryam Kaffash Jamshid**. The complete upstream license is
included in `docs/licenses/EIS-studio-MIT.txt`; SHA-256 hashes are recorded in
`docs/licenses/eis-provenance.json` and checked by the regression suite.

## Dependencies

Qt, Python, NumPy and SciPy are separately licensed dependencies. No Qt or Python
binary runtime is included in the GitHub source archive. Windows release packages
bundle runtimes; their dependency notices are described in
`packaging/windows/THIRD_PARTY_NOTICES.txt`. Preserve the license files carried by
Python wheels and Qt distributions when distributing those binaries.

## Artwork

`docs/assets/pytro-nova-knight.png` is the original image supplied by Ali Afruz,
included unchanged at his request. It is conceptual project artwork, not a
scientific measurement or a screenshot. No generated replacement banner is used.
