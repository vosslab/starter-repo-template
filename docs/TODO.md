REPO_STYLE.md ships to other repos, make sure REPO_STYLE.md does not contain information relavent to only this repo, like 
repolib

dist_clean.sh does not clean enough, it should clean up ALL repo types, include .venv folders, .egg folders for pypi and 
other things

make a RUST_STYLE.md based on the Klabnik S. The Rust Programming Language 3ed 2026 book and online sources like 
https://doc.rust-lang.org/stable/style-guide/principles.html
https://rustwiki.org/en/style-guide/index.html
https://www.compilenrun.com/docs/language/rust/rust-best-practices/rust-style-guide/
https://www.codelessgenie.com/rust-tutorial/rust-best-practices-coding-standards-and-style-guide/
make sure that the RUST style aligns with the REPO_STYLE.md core principles

default artwork license should be none, instead of CC BY in the reset_repo.py interactive interview 


add 
/OTHER_REPOS/
/LOCAL_ONLY/
to universal .gitignore
