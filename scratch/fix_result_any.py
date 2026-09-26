with open("src/before_you_pay/services/result.py", encoding="utf-8") as f:
    code = f.read()

code = code.replace(
    "from uuid import UUID, uuid4", "from typing import Any\nfrom uuid import UUID, uuid4"
)

with open("src/before_you_pay/services/result.py", "w", encoding="utf-8") as f:
    f.write(code)
print("Added Any to result.py")
