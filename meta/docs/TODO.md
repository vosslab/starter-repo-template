1. make the .gitignore local block more clear, the block ordering is not intuitive at the moment

2. pytest.ini is not supposed to live through reset_repo.py interview but it does

3. reset_repo.py should automatically stage the commit and push, perhaps a single confirm prompt with default Yes, but too many agents fail to finish the reset.

4. many agents argue that  tests/test_test_checkout_disk_budget.py should be an e2e test and remove it, I want it baselevel to be used with `source source_me.sh && pytest tests/` show make sure that it is documented in the file header with the clear vendored message that even if you remove this it will come back

5. too many agents confuse the tools/ folder for someplace to put the main code. (1) survey the local repos in ~/nsh/ for misuse of tools/ (2) we need a tools/TOOLS_README.md that ships. (3) perhaps a pytest script that checks to make sure no script in tools/ or devel/ is every imported (4) be sure the tools/TOOLS_README.md and devel/DEVEL_README.md are cross referenced and compliment each other.

6. I want to limited the number of scripts (py/sh) and executable files in repo root. I am not sure on the counts, but I was thinking to enforce less than 7 scripts/executable files and warn when there are 5 or more
