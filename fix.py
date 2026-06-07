import re

with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 将字面意义的反斜杠+n 替换为真正的换行符
# 注意：这里替换的是两个字符 \ 和 n 连续出现的情况
fixed = content.replace('\\n', '\n')

# 可选：如果存在 \r\n 被写成 \\r\\n 的情况，一并修复
fixed = fixed.replace('\\r\\n', '\r\n')

with open('main.py', 'w', encoding='utf-8') as f:
    f.write(fixed)

print("main.py 修复完成")