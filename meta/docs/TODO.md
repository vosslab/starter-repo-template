1. have graphify_map_repo.py allow both -F and -S or -U and -S on same run

2. have graphify_map_repo.py generated a docs/GRAPHIFY.md that includes the svg docs/GRAPHIFY_map.svg at the top 
of the page but then has markdown text that describe the content, the repo groups, and other interesting graph 
topics

3. too many agents confuse the tools/ folder for someplace to put the main code. (1) survey the local repos in 
~/nsh/ for misuse of tools/ (2) we need a tools/TOOLS_README.md that ships. (3) perhaps a pytest script that 
checks to make sure no script in tools/ or devel/ is every imported (4) be sure the tools/TOOLS_README.md and 
devel/DEVEL_README.md are cross referenced and compliment each other.

