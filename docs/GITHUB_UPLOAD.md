# Upload Pytro-NOVA to GitHub

Suggested repository name: **Pytro-NOVA**. The prepared repository is not pushed
automatically. Create an empty repository in your GitHub account, then use the
repository URL GitHub gives you:

```bash
cd /path/to/Pytro-NOVA
git init -b main
git add .
git status --short
git commit -m "Release Pytro-NOVA 3.9.5"
git remote add origin YOUR_REPOSITORY_URL
git push -u origin main
```

Configure your own Git name/email if Git requests it. The repository root should
contain `.github/`, `CMakeLists.txt`, `app/` and `backend/` directly. Do not upload
the outer delivery folder, local build trees, Python environments, or real `.nox`
measurement files. The included CSV examples are synthetic.

After the first push, check **Actions**: Linux builds a `.deb`, and Windows builds
the native executable, portable runtime ZIP and per-user installer. Source tests
also run on both operating systems. The Windows build is not verified merely by
passing Linux tests; wait for the Windows workflow to succeed before distributing
its artifacts. Unsigned Windows executables can display SmartScreen warnings.

The README uses the original artwork from `docs/assets/pytro-nova-knight.png`.
Real measurement files used for local validation are deliberately absent.
