with open("src/cvcutter/core/orchestrator.py", "r") as f:
    content = f.read()
import re

content = re.sub(r'<<<<<<< HEAD\n', '', content)
content = re.sub(r'=======\n', '', content)
content = re.sub(r'>>>>>>> origin/refactor-architecture-and-ui-17417017401751256998\n', '', content)
with open("src/cvcutter/core/orchestrator.py", "w") as f:
    f.write(content)

with open("src/cvcutter/ui/views.py", "r") as f:
    content = f.read()
content = re.sub(r'<<<<<<< HEAD\n', '', content)
content = re.sub(r'=======\n', '', content)
content = re.sub(r'>>>>>>> origin/refactor-architecture-and-ui-17417017401751256998\n', '', content)
with open("src/cvcutter/ui/views.py", "w") as f:
    f.write(content)
