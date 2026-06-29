Output ../gifs/demo.gif

Set Height 730
Set Width 1460

Hide

Type "export PATH=~/.local/bin:$PATH"
Enter

Type 'alias python="uv run ~/.config/python/repl.py"'
Enter

Type "demo_dir=${PWD}/akebi-vhs-demo"
Enter

Type "rm -rf ${demo_dir} && mkdir ${demo_dir}"
Enter

Type "cd ${demo_dir}"
Enter

Type "echo '*' > .gitignore"
Enter

Type "export IPYTHONDIR=${PWD}/.ipython"
Enter

Type "mkdir -p ${IPYTHONDIR}/profile_default/startup"
Enter

Type `echo 'get_ipython().ast_node_interactivity = "none"' >> ${IPYTHONDIR}/profile_default/startup/startup.py`
Enter  

Type "rm -rf ~/.cache/akebi"
Enter

Type "clear"
Enter

Show

Type "python"
Enter

Wait /.*In.*:.*/
Sleep 0.5s

Type "from akebi import Bun"
Enter

Wait /.*In.*:.*/
Sleep 0.5s

Type "bun = Bun()"
Enter

Wait /.*In.*:.*/
Sleep 0.5s

Type 'bun(["init", "--yes"])'
Enter

Wait /.*In.*:.*/
Sleep 0.5s

Type 'bun(["run", "index.ts"])'
Enter

Wait /.*In.*:.*/

Sleep 5s

Hide

Type "cd ~"

Type "rm -rf ${demo_dir}"
Enter